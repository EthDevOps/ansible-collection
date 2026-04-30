#!/usr/bin/env python3
"""
ASUS ROG Astral RTX 5090/5080 Per-Pin Power Monitor for Linux

Reads per-pin voltage and current from the ITE IT8915FN chip on ASUS ROG Astral
GPUs via the Linux i2c-dev interface. This is the Linux equivalent of what
GPU Tweak III's "Power Detector+" shows on Windows.

Requires: root or i2c group membership for /dev/i2c-* access
"""

import argparse
import ctypes
import fcntl
import glob
import json
import os
import struct
import subprocess
import sys
import time

# ITE IT8915FN constants
IT8915_I2C_ADDR = 0x2B
IT8915_POWER_REG = 0x80
IT8915_POWER_LEN = 24  # 6 pins × 4 bytes (2B voltage + 2B current)
IT8915_EXTRA_REG = 0x98
IT8915_EXTRA_LEN = 8   # 2 extra rails × 4 bytes

# Linux i2c-dev ioctl constants
I2C_SLAVE = 0x0703
I2C_SMBUS = 0x0720
I2C_SMBUS_READ = 1
I2C_SMBUS_BYTE_DATA = 2

# ASUS default per-pin current warning threshold (amps)
DEFAULT_ALERT_THRESHOLD = 9.2

# Voltage sanity range for IT8915 detection (millivolts)
VOLTAGE_SANITY_MIN = 10000  # 10V
VOLTAGE_SANITY_MAX = 14000  # 14V


# SMBus ioctl structures
class _i2c_smbus_data(ctypes.Union):
    _fields_ = [
        ("byte", ctypes.c_ubyte),
        ("word", ctypes.c_ushort),
        ("block", ctypes.c_ubyte * 34),
    ]


class _i2c_smbus_ioctl_data(ctypes.Structure):
    _fields_ = [
        ("read_write", ctypes.c_ubyte),
        ("command", ctypes.c_ubyte),
        ("size", ctypes.c_uint),
        ("data", ctypes.POINTER(_i2c_smbus_data)),
    ]


def i2c_open(bus_num):
    """Open an i2c bus device."""
    path = f"/dev/i2c-{bus_num}"
    try:
        fd = os.open(path, os.O_RDWR)
        return fd
    except OSError as e:
        raise RuntimeError(f"Cannot open {path}: {e}. Run as root or add user to i2c group.")


def i2c_set_slave(fd, addr):
    """Set the i2c slave address."""
    fcntl.ioctl(fd, I2C_SLAVE, addr)


def _smbus_read_byte(fd, reg):
    """Read a single byte via SMBus byte-data protocol."""
    data = _i2c_smbus_data()
    args = _i2c_smbus_ioctl_data(
        read_write=I2C_SMBUS_READ,
        command=reg,
        size=I2C_SMBUS_BYTE_DATA,
        data=ctypes.pointer(data),
    )
    fcntl.ioctl(fd, I2C_SMBUS, args)
    return data.byte


def i2c_read_bytes(fd, reg, length):
    """Read a sequence of bytes using SMBus byte-data reads."""
    data = bytearray()
    for i in range(length):
        data.append(_smbus_read_byte(fd, reg + i))
    return bytes(data)


def discover_gpu_buses():
    """
    Discover NVIDIA GPU i2c buses by scanning sysfs.
    Returns list of (bus_num, pci_addr) for NVIDIA i2c adapter 1 on each GPU.
    """
    buses = []
    for path in sorted(glob.glob("/sys/bus/i2c/devices/i2c-*/name")):
        try:
            with open(path) as f:
                name = f.read().strip()
        except OSError:
            continue

        # Match "NVIDIA i2c adapter 1 at XX:00.0"
        if name.startswith("NVIDIA i2c adapter 1 at "):
            pci_addr = name.split(" at ")[1]
            bus_dir = os.path.basename(os.path.dirname(path))
            bus_num = int(bus_dir.split("-")[1])
            buses.append((bus_num, pci_addr))

    return buses


def get_nvidia_smi_gpu_map():
    """
    Get GPU index to PCI address mapping from nvidia-smi.
    Returns dict of {pci_bus_hex: gpu_index}.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,pci.bus_id", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {}

        mapping = {}
        for line in result.stdout.strip().split("\n"):
            parts = line.split(", ")
            if len(parts) == 2:
                idx = int(parts[0].strip())
                # PCI bus ID format from nvidia-smi: 00000000:F1:00.0
                pci_full = parts[1].strip()
                # Extract bus number and normalize (strip leading zeros)
                # e.g., "01" -> "1", "F1" -> "f1"
                pci_bus = pci_full.split(":")[1].lower().lstrip("0") or "0"
                mapping[pci_bus] = idx
        return mapping
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}


def probe_it8915(bus_num):
    """
    Probe for IT8915 at the given i2c bus.
    Returns True if a valid power reading is found.
    """
    try:
        fd = i2c_open(bus_num)
        try:
            i2c_set_slave(fd, IT8915_I2C_ADDR)
            data = i2c_read_bytes(fd, IT8915_POWER_REG, 4)
            if len(data) >= 2:
                voltage_mv = struct.unpack(">H", data[0:2])[0]
                return VOLTAGE_SANITY_MIN <= voltage_mv <= VOLTAGE_SANITY_MAX
        finally:
            os.close(fd)
    except (OSError, RuntimeError):
        return False
    return False


def read_pin_power(fd):
    """
    Read the 6-pin power data from IT8915.
    Returns list of (pin_num, voltage_V, current_A) in pin order 1-6.
    """
    data = i2c_read_bytes(fd, IT8915_POWER_REG, IT8915_POWER_LEN)
    if len(data) < IT8915_POWER_LEN:
        raise RuntimeError(f"Short read: got {len(data)} bytes, expected {IT8915_POWER_LEN}")

    pins = []
    for rail in range(6):
        pin = 6 - rail  # reversed: rail 0 = pin 6, rail 5 = pin 1
        offset = rail * 4
        voltage_mv = struct.unpack(">H", data[offset:offset + 2])[0]
        current_ma = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        pins.append((pin, voltage_mv / 1000.0, current_ma / 1000.0))

    # Sort by pin number
    pins.sort(key=lambda x: x[0])
    return pins


def read_extra_rails(fd):
    """
    Read the extra rail data from IT8915 (registers 0x98-0xA3).
    Returns list of (label, voltage_V, current_A).
    """
    data = i2c_read_bytes(fd, IT8915_EXTRA_REG, IT8915_EXTRA_LEN)
    if len(data) < IT8915_EXTRA_LEN:
        return []

    rails = []
    labels = ["Rail 7", "Rail 8"]
    for i in range(2):
        offset = i * 4
        voltage_mv = struct.unpack(">H", data[offset:offset + 2])[0]
        current_ma = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        if VOLTAGE_SANITY_MIN <= voltage_mv <= VOLTAGE_SANITY_MAX or current_ma > 0:
            rails.append((labels[i], voltage_mv / 1000.0, current_ma / 1000.0))

    return rails


class AstralPowerMonitor:
    """Manages discovery and reading of ASUS Astral GPU power sensors."""

    def __init__(self):
        self.gpus = []  # list of (gpu_index, bus_num, pci_addr)
        self._fds = {}  # bus_num -> fd

    def discover(self):
        """Discover all Astral GPUs with IT8915 power monitoring."""
        buses = discover_gpu_buses()
        gpu_map = get_nvidia_smi_gpu_map()

        for bus_num, pci_addr in buses:
            if not probe_it8915(bus_num):
                continue

            # Try to match to nvidia-smi GPU index
            pci_bus = pci_addr.split(":")[0].lower()
            gpu_idx = gpu_map.get(pci_bus, -1)

            self.gpus.append((gpu_idx, bus_num, pci_addr))

        # Sort by GPU index
        self.gpus.sort(key=lambda x: x[0] if x[0] >= 0 else 999)

    def _get_fd(self, bus_num):
        """Get or open an fd for the given bus."""
        if bus_num not in self._fds:
            fd = i2c_open(bus_num)
            i2c_set_slave(fd, IT8915_I2C_ADDR)
            self._fds[bus_num] = fd
        return self._fds[bus_num]

    def read_all(self):
        """
        Read power data from all discovered GPUs.
        Returns list of dicts with gpu_index, pci_addr, pins, extra_rails, totals.
        """
        results = []
        for gpu_idx, bus_num, pci_addr in self.gpus:
            try:
                fd = self._get_fd(bus_num)
                pins = read_pin_power(fd)
                extra = read_extra_rails(fd)

                total_power = sum(v * a for _, v, a in pins)
                total_current = sum(a for _, _, a in pins)
                avg_voltage = sum(v for _, v, _ in pins) / len(pins) if pins else 0

                results.append({
                    "gpu_index": gpu_idx,
                    "pci_addr": pci_addr,
                    "bus": bus_num,
                    "pins": [
                        {"pin": p, "voltage_v": round(v, 3), "current_a": round(a, 3),
                         "power_w": round(v * a, 2)}
                        for p, v, a in pins
                    ],
                    "extra_rails": [
                        {"label": l, "voltage_v": round(v, 3), "current_a": round(a, 3),
                         "power_w": round(v * a, 2)}
                        for l, v, a in extra
                    ],
                    "total_connector_power_w": round(total_power, 2),
                    "total_connector_current_a": round(total_current, 2),
                    "avg_voltage_v": round(avg_voltage, 3),
                })
            except (OSError, RuntimeError) as e:
                results.append({
                    "gpu_index": gpu_idx,
                    "pci_addr": pci_addr,
                    "bus": bus_num,
                    "error": str(e),
                })

        return results

    def close(self):
        """Close all open file descriptors."""
        for fd in self._fds.values():
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds.clear()


def format_table(results, alert_threshold=None):
    """Format results as a human-readable table."""
    lines = []
    for gpu in results:
        if "error" in gpu:
            lines.append(f"GPU {gpu['gpu_index']} ({gpu['pci_addr']}): ERROR - {gpu['error']}")
            lines.append("")
            continue

        idx = gpu["gpu_index"]
        label = f"GPU {idx}" if idx >= 0 else f"GPU ? (PCI {gpu['pci_addr']})"
        lines.append(f"{label}  [i2c-{gpu['bus']}]")
        lines.append(f"{'─' * 52}")
        lines.append(f"  {'Pin':>4}  {'Voltage':>9}  {'Current':>9}  {'Power':>8}")
        lines.append(f"  {'───':>4}  {'─────────':>9}  {'─────────':>9}  {'────────':>8}")

        for pin in gpu["pins"]:
            alert = ""
            if alert_threshold and pin["current_a"] >= alert_threshold:
                alert = " ⚠ OVER THRESHOLD"
            lines.append(
                f"  {pin['pin']:>4}  {pin['voltage_v']:>8.3f}V  {pin['current_a']:>8.3f}A  {pin['power_w']:>7.2f}W{alert}"
            )

        lines.append(f"  {'───':>4}  {'─────────':>9}  {'─────────':>9}  {'────────':>8}")
        lines.append(
            f"  {'Tot':>4}  {gpu['avg_voltage_v']:>8.3f}V  {gpu['total_connector_current_a']:>8.3f}A  {gpu['total_connector_power_w']:>7.2f}W"
        )

        if gpu.get("extra_rails"):
            lines.append("")
            for rail in gpu["extra_rails"]:
                lines.append(
                    f"  {rail['label']:>4}  {rail['voltage_v']:>8.3f}V  {rail['current_a']:>8.3f}A  {rail['power_w']:>7.2f}W"
                )

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="ASUS ROG Astral RTX 5090/5080 Per-Pin Power Monitor (Linux)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  sudo %(prog)s                  # single reading, all GPUs
  sudo %(prog)s -w 1             # continuous monitoring, 1s interval
  sudo %(prog)s --json           # JSON output (single shot)
  sudo %(prog)s --json -w 2      # JSON output, 2s interval
  sudo %(prog)s --alert 9.2      # warn if any pin exceeds 9.2A
  sudo %(prog)s -g 0             # monitor only GPU 0
""",
    )
    parser.add_argument("-w", "--watch", type=float, metavar="SEC",
                        help="continuous monitoring interval in seconds")
    parser.add_argument("--json", action="store_true",
                        help="output as JSON")
    parser.add_argument("--alert", type=float, metavar="AMPS",
                        help=f"alert threshold per pin in amps (default: {DEFAULT_ALERT_THRESHOLD})")
    parser.add_argument("-g", "--gpu", type=int, metavar="IDX",
                        help="monitor only this GPU index")
    parser.add_argument("--extra", action="store_true",
                        help="include extra rail readings (0x98-0xA3)")
    args = parser.parse_args()

    monitor = AstralPowerMonitor()
    monitor.discover()

    if not monitor.gpus:
        print("No ASUS Astral GPUs with IT8915 power monitoring found.", file=sys.stderr)
        print("Make sure:", file=sys.stderr)
        print("  1. You have ASUS ROG Astral RTX 5080/5090 GPU(s)", file=sys.stderr)
        print("  2. NVIDIA driver is loaded (i2c buses exist)", file=sys.stderr)
        print("  3. Running as root or user is in i2c group", file=sys.stderr)
        sys.exit(1)

    # Filter to specific GPU if requested
    if args.gpu is not None:
        monitor.gpus = [(i, b, p) for i, b, p in monitor.gpus if i == args.gpu]
        if not monitor.gpus:
            print(f"GPU {args.gpu} not found or has no IT8915 sensor.", file=sys.stderr)
            sys.exit(1)

    # If --extra not set, we skip extra rails in output
    show_extra = args.extra

    try:
        first = True
        while True:
            results = monitor.read_all()

            if not show_extra:
                for r in results:
                    r.pop("extra_rails", None)

            if args.json:
                ts = {"timestamp": time.time(), "gpus": results}
                print(json.dumps(ts))
                if not args.watch:
                    break
            else:
                if not first and args.watch:
                    # Move cursor up to overwrite
                    line_count = sum(
                        9 + (3 if show_extra and r.get("extra_rails") else 0)
                        for r in results
                    )
                    print(f"\033[{line_count}A", end="")

                output = format_table(results, alert_threshold=args.alert)
                print(output, end="")

                if first:
                    first = False

                if not args.watch:
                    break

            sys.stdout.flush()
            time.sleep(args.watch)

    except KeyboardInterrupt:
        print()
    finally:
        monitor.close()


if __name__ == "__main__":
    main()
