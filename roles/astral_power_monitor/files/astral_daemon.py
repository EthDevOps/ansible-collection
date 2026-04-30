#!/usr/bin/env python3
"""
Astral Power Monitor Daemon

Continuous monitoring daemon with Prometheus metrics export and fire-hazard
detection for ASUS ROG Astral RTX 5090/5080 GPUs.

Reads per-pin voltage/current from the ITE IT8915FN chip, exposes metrics
for Prometheus scraping, and can throttle GPU power on critical imbalance.
"""

import argparse
import logging
import math
import os
import signal
import subprocess
import sys
import time

import yaml
from prometheus_client import Gauge, Info, start_http_server

from astral_power_monitor import AstralPowerMonitor

log = logging.getLogger("astral-daemon")

# ---------------------------------------------------------------------------
# Default config (overridden by YAML)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "poll_interval": 1.0,
    "prometheus": {
        "enabled": True,
        "host": "0.0.0.0",
        "port": 9101,
    },
    "fire_hazard": {
        "enabled": True,
        "warning_stddev": 0.1,
        "critical_stddev": 0.5,
        "pin_current_warning": 8.0,
        "pin_current_critical": 9.2,
        "throttle_power_limit_watts": 250,
        "restore_on_clear": True,
        "critical_count_before_throttle": 3,
    },
    "read_extra_rails": True,
    "log_level": "INFO",
}


def deep_merge(base, override):
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path):
    """Load and merge YAML config with defaults."""
    if path and os.path.exists(path):
        with open(path) as f:
            user = yaml.safe_load(f) or {}
        return deep_merge(DEFAULT_CONFIG, user)
    return DEFAULT_CONFIG.copy()


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
class Metrics:
    def __init__(self):
        labels = ["gpu"]
        pin_labels = ["gpu", "pin"]

        self.pin_voltage = Gauge(
            "astral_pin_voltage_volts",
            "Per-pin voltage on the 12V-2x6 connector",
            pin_labels,
        )
        self.pin_current = Gauge(
            "astral_pin_current_amps",
            "Per-pin current on the 12V-2x6 connector",
            pin_labels,
        )
        self.pin_power = Gauge(
            "astral_pin_power_watts",
            "Per-pin power on the 12V-2x6 connector",
            pin_labels,
        )
        self.connector_power = Gauge(
            "astral_connector_power_watts",
            "Total connector power (sum of 6 pins)",
            labels,
        )
        self.connector_current = Gauge(
            "astral_connector_current_amps",
            "Total connector current (sum of 6 pins)",
            labels,
        )
        self.avg_voltage = Gauge(
            "astral_connector_voltage_volts",
            "Average connector voltage across 6 pins",
            labels,
        )
        self.pin_current_stddev = Gauge(
            "astral_pin_current_stddev_amps",
            "Standard deviation of pin currents (imbalance indicator)",
            labels,
        )
        self.alert_state = Gauge(
            "astral_alert_state",
            "Fire-hazard alert state: 0=ok, 1=warning, 2=critical",
            labels,
        )
        self.power_limit = Gauge(
            "astral_enforced_power_limit_watts",
            "Enforced GPU power limit (0 = not throttled)",
            labels,
        )
        self.extra_voltage = Gauge(
            "astral_extra_rail_voltage_volts",
            "Extra rail voltage",
            ["gpu", "rail"],
        )
        self.extra_current = Gauge(
            "astral_extra_rail_current_amps",
            "Extra rail current",
            ["gpu", "rail"],
        )
        self.extra_power = Gauge(
            "astral_extra_rail_power_watts",
            "Extra rail power",
            ["gpu", "rail"],
        )
        self.info = Info(
            "astral_monitor",
            "Astral power monitor metadata",
        )
        self.info.info({"version": "1.0.0", "chip": "ITE IT8915FN"})

    def update(self, gpu_data, alert_states, power_limits):
        """Push a full reading into Prometheus gauges."""
        for gpu in gpu_data:
            if "error" in gpu:
                continue
            g = str(gpu["gpu_index"])

            for pin in gpu["pins"]:
                p = str(pin["pin"])
                self.pin_voltage.labels(gpu=g, pin=p).set(pin["voltage_v"])
                self.pin_current.labels(gpu=g, pin=p).set(pin["current_a"])
                self.pin_power.labels(gpu=g, pin=p).set(pin["power_w"])

            self.connector_power.labels(gpu=g).set(gpu["total_connector_power_w"])
            self.connector_current.labels(gpu=g).set(gpu["total_connector_current_a"])
            self.avg_voltage.labels(gpu=g).set(gpu["avg_voltage_v"])
            self.pin_current_stddev.labels(gpu=g).set(gpu.get("pin_current_stddev", 0))
            self.alert_state.labels(gpu=g).set(alert_states.get(gpu["gpu_index"], 0))
            self.power_limit.labels(gpu=g).set(power_limits.get(gpu["gpu_index"], 0))

            for rail in gpu.get("extra_rails", []):
                r = rail["label"]
                self.extra_voltage.labels(gpu=g, rail=r).set(rail["voltage_v"])
                self.extra_current.labels(gpu=g, rail=r).set(rail["current_a"])
                self.extra_power.labels(gpu=g, rail=r).set(rail["power_w"])


# ---------------------------------------------------------------------------
# Fire-hazard detection and GPU throttling
# ---------------------------------------------------------------------------
def compute_stddev(values):
    """Population standard deviation."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    return math.sqrt(variance)


def get_default_power_limit(gpu_index):
    """Query the default (max) power limit for a GPU via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-i", str(gpu_index),
             "--query-gpu=power.default_limit", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass
    return None


def set_power_limit(gpu_index, watts):
    """Set GPU power limit via nvidia-smi. Returns True on success."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-i", str(gpu_index), "-pl", str(int(watts))],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            log.warning("GPU %d: power limit set to %dW", gpu_index, int(watts))
            return True
        log.error("GPU %d: failed to set power limit: %s",
                  gpu_index, result.stderr.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.error("GPU %d: nvidia-smi error setting power limit: %s", gpu_index, e)
    return False


class FireHazardDetector:
    """Tracks per-GPU alert state and applies throttling."""

    # Alert levels
    OK = 0
    WARNING = 1
    CRITICAL = 2

    def __init__(self, config):
        self.cfg = config
        self.alert_states = {}        # gpu_index -> alert level
        self.critical_counts = {}     # gpu_index -> consecutive critical count
        self.power_limits = {}        # gpu_index -> enforced limit (0 = none)
        self.default_limits = {}      # gpu_index -> original power limit
        self.throttled = set()        # set of gpu_index currently throttled

    def evaluate(self, gpu_data):
        """
        Evaluate fire-hazard state for each GPU.
        Mutates gpu_data to add pin_current_stddev.
        Returns (alert_states, power_limits) dicts.
        """
        for gpu in gpu_data:
            if "error" in gpu:
                continue

            idx = gpu["gpu_index"]
            currents = [p["current_a"] for p in gpu["pins"]]
            stddev = compute_stddev(currents)
            gpu["pin_current_stddev"] = round(stddev, 4)
            max_current = max(currents) if currents else 0

            prev_state = self.alert_states.get(idx, self.OK)
            new_state = self.OK

            # Check stddev thresholds
            if stddev >= self.cfg["critical_stddev"]:
                new_state = self.CRITICAL
            elif stddev >= self.cfg["warning_stddev"]:
                new_state = max(new_state, self.WARNING)

            # Check absolute per-pin thresholds
            if max_current >= self.cfg["pin_current_critical"]:
                new_state = self.CRITICAL
            elif max_current >= self.cfg["pin_current_warning"]:
                new_state = max(new_state, self.WARNING)

            # Track consecutive critical readings
            if new_state == self.CRITICAL:
                self.critical_counts[idx] = self.critical_counts.get(idx, 0) + 1
            else:
                self.critical_counts[idx] = 0

            # Log state transitions
            if new_state != prev_state:
                labels = {self.OK: "OK", self.WARNING: "WARNING", self.CRITICAL: "CRITICAL"}
                log.log(
                    logging.WARNING if new_state > self.OK else logging.INFO,
                    "GPU %d: alert state %s -> %s (stddev=%.3fA, max_pin=%.3fA)",
                    idx, labels[prev_state], labels[new_state], stddev, max_current,
                )

            self.alert_states[idx] = new_state

            # Throttle on sustained critical
            throttle_limit = self.cfg.get("throttle_power_limit_watts", 0)
            count_threshold = self.cfg.get("critical_count_before_throttle", 3)

            if (new_state == self.CRITICAL
                    and throttle_limit > 0
                    and self.critical_counts[idx] >= count_threshold
                    and idx not in self.throttled):
                # Save default limit before throttling
                if idx not in self.default_limits:
                    self.default_limits[idx] = get_default_power_limit(idx)
                if set_power_limit(idx, throttle_limit):
                    self.throttled.add(idx)
                    self.power_limits[idx] = throttle_limit
                    log.critical(
                        "GPU %d: THROTTLED to %dW due to critical pin imbalance "
                        "(stddev=%.3fA, max_pin=%.3fA)",
                        idx, throttle_limit, stddev, max_current,
                    )

            # Restore on clear
            if (new_state == self.OK
                    and idx in self.throttled
                    and self.cfg.get("restore_on_clear", True)):
                default = self.default_limits.get(idx)
                if default and set_power_limit(idx, default):
                    self.throttled.discard(idx)
                    self.power_limits[idx] = 0
                    log.info("GPU %d: power limit restored to %dW", idx, int(default))

            # Update power_limits for non-throttled GPUs
            if idx not in self.throttled:
                self.power_limits[idx] = 0

        return self.alert_states, self.power_limits


# ---------------------------------------------------------------------------
# Daemon main loop
# ---------------------------------------------------------------------------
class Daemon:
    def __init__(self, config):
        self.config = config
        self.running = True
        self.monitor = AstralPowerMonitor()
        self.metrics = None
        self.hazard = None

    def _handle_signal(self, signum, frame):
        log.info("Received signal %d, shutting down", signum)
        self.running = False

    def run(self):
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Setup logging
        level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Discover GPUs
        self.monitor.discover()
        if not self.monitor.gpus:
            log.error("No ASUS Astral GPUs with IT8915 power monitoring found")
            return 1

        gpu_list = ", ".join(
            f"GPU {i} (PCI {p}, i2c-{b})" for i, b, p in self.monitor.gpus
        )
        log.info("Discovered %d GPU(s): %s", len(self.monitor.gpus), gpu_list)

        # Start Prometheus HTTP server
        prom_cfg = self.config.get("prometheus", {})
        if prom_cfg.get("enabled", True):
            self.metrics = Metrics()
            port = prom_cfg.get("port", 9101)
            host = prom_cfg.get("host", "0.0.0.0")
            start_http_server(port, addr=host)
            log.info("Prometheus metrics server listening on %s:%d", host, port)

        # Fire-hazard detector
        fh_cfg = self.config.get("fire_hazard", {})
        if fh_cfg.get("enabled", True):
            self.hazard = FireHazardDetector(fh_cfg)
            log.info(
                "Fire-hazard detection enabled (warn=%.2fA stddev, crit=%.2fA stddev, "
                "throttle=%dW)",
                fh_cfg.get("warning_stddev", 0.1),
                fh_cfg.get("critical_stddev", 0.5),
                fh_cfg.get("throttle_power_limit_watts", 0),
            )

        poll_interval = self.config.get("poll_interval", 1.0)
        log.info("Polling every %.1fs", poll_interval)

        read_extra = self.config.get("read_extra_rails", True)
        alert_states = {}
        power_limits = {}

        try:
            while self.running:
                t0 = time.monotonic()

                results = self.monitor.read_all()
                if not read_extra:
                    for r in results:
                        r.pop("extra_rails", None)

                # Fire-hazard evaluation
                if self.hazard:
                    alert_states, power_limits = self.hazard.evaluate(results)
                else:
                    # Still compute stddev for prometheus even without hazard detection
                    for gpu in results:
                        if "error" not in gpu:
                            currents = [p["current_a"] for p in gpu["pins"]]
                            gpu["pin_current_stddev"] = round(compute_stddev(currents), 4)

                # Update Prometheus
                if self.metrics:
                    self.metrics.update(results, alert_states, power_limits)

                # Sleep for remainder of interval
                elapsed = time.monotonic() - t0
                sleep_time = max(0, poll_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        finally:
            # Restore power limits on shutdown
            if self.hazard:
                for idx in list(self.hazard.throttled):
                    default = self.hazard.default_limits.get(idx)
                    if default:
                        set_power_limit(idx, default)
                        log.info("GPU %d: power limit restored to %dW on shutdown",
                                 idx, int(default))
            self.monitor.close()

        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Astral Power Monitor Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  sudo %(prog)s                           # run with default config
  sudo %(prog)s -c /etc/astral/config.yaml  # run with custom config
  sudo %(prog)s --validate                 # validate config and exit
""",
    )
    parser.add_argument("-c", "--config", metavar="PATH",
                        default="/etc/astral-power-monitor.yaml",
                        help="path to YAML config file (default: %(default)s)")
    parser.add_argument("--validate", action="store_true",
                        help="validate config and exit")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.validate:
        import json as _json
        print("Loaded config:")
        print(_json.dumps(config, indent=2))

        # Quick validation
        errors = []
        if config["poll_interval"] <= 0:
            errors.append("poll_interval must be > 0")
        fh = config.get("fire_hazard", {})
        if fh.get("enabled"):
            if fh.get("warning_stddev", 0) >= fh.get("critical_stddev", 1):
                errors.append("warning_stddev must be < critical_stddev")
            if fh.get("pin_current_warning", 0) >= fh.get("pin_current_critical", 1):
                errors.append("pin_current_warning must be < pin_current_critical")

        if errors:
            print("\nValidation errors:")
            for e in errors:
                print(f"  - {e}")
            return 1
        print("\nConfig is valid.")
        return 0

    daemon = Daemon(config)
    return daemon.run()


if __name__ == "__main__":
    sys.exit(main())
