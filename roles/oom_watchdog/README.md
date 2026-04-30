# OOM Watchdog Role

Installs and configures the Linux `watchdog` daemon together with the `softdog` kernel module so that an unresponsive host (e.g. one stuck in memory-reclaim thrashing before the OOM killer fires) is automatically rebooted.

## Background

`vm.panic_on_oom` alone is insufficient on memory-pressured hosts: the system can become unresponsive long before the OOM killer is invoked, because the kernel spends all its time in reclaim loops. A watchdog covers that gap by force-rebooting the host if userspace stops responding.

This role was developed for bare-metal GPU hosts running heavy workloads (`ere-server`, `moongate-server`, etc.) that consume tens of GB of RAM each and have triggered repeated lockups.

## Requirements

- Debian-based target (Debian, Ubuntu 22.04 / 24.04)
- `community.general` and `ansible.posix` collections (already used elsewhere in this collection)

## What the role does

1. Installs the `watchdog` apt package.
2. Writes `/etc/modules-load.d/softdog.conf` and loads the `softdog` kernel module.
3. Sets `kernel.nmi_watchdog = 1` via `/etc/sysctl.d/60-oom-watchdog.conf` (optional, on by default).
4. Templates `/etc/watchdog.conf` from role variables.
5. Enables and starts the `watchdog` systemd service, restarting it on config changes.

## Role Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `oom_watchdog_device` | `/dev/watchdog` | Watchdog device the daemon pings. `softdog` exposes this. |
| `oom_watchdog_timeout` | `60` | Seconds the kernel watchdog waits without a ping before forcing a reboot. |
| `oom_watchdog_interval` | `30` | Seconds between liveness checks performed by the watchdog daemon. Must be less than `oom_watchdog_timeout`. |
| `oom_watchdog_min_memory` | `1` | Reboot when fewer than this many free pages are available — catches runaway-memory lockups before the OOM killer can act. |
| `oom_watchdog_max_load_1_per_core` | `4` | Per-core 1-minute load threshold. The rendered `max-load-1` is this value multiplied by `ansible_processor_vcpus`, so the threshold scales automatically with host size (e.g. `4` × 32 vCPUs ⇒ `max-load-1 = 128`). |
| `oom_watchdog_realtime` | `true` | Run the daemon with realtime scheduling so it keeps pinging the watchdog under heavy load. |
| `oom_watchdog_priority` | `1` | Realtime priority used when `oom_watchdog_realtime` is enabled. |
| `oom_watchdog_nmi_enabled` | `true` | Set `kernel.nmi_watchdog = 1` so the kernel itself can detect hard lockups. Disable on hosts where the NMI watchdog is unwanted (e.g. some virtualized environments). |

## Example Playbook

```yaml
- hosts: gpu_baremetal
  roles:
    - role: oom_watchdog
      vars:
        oom_watchdog_timeout: 90
        oom_watchdog_interval: 30
        oom_watchdog_max_load_1_per_core: 6
```

## Verification

After deployment:

```sh
systemctl status watchdog
lsmod | grep softdog
cat /proc/sys/kernel/nmi_watchdog
```

To validate the watchdog actually reboots the host, trigger a sysrq-style hang on a non-production system (`echo c > /proc/sysrq-trigger`) and confirm the reboot occurs within `oom_watchdog_timeout` seconds. **Do not run this on production hosts.**

## License

MIT
