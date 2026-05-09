# Astral Power Monitor Role

Deploys the Astral per-pin power monitor as a systemd service on hosts with ASUS ROG Astral RTX 5090 / 5080 GPUs. The daemon reads per-pin voltage and current from the on-card ITE IT8915FN chip, exposes Prometheus metrics, and can throttle GPU power if it detects an imbalance that suggests an impending 12VHPWR fire-hazard condition.

## Background

ASUS ROG Astral cards expose per-pin telemetry over i2c via the IT8915FN. Imbalance across the 12VHPWR connector pins is an early indicator of melting connectors — a known failure mode on this card class. This role automates installation of a long-running daemon that continuously samples that telemetry, feeds it into Prometheus, and (optionally) clamps the card's power limit through `nvidia-smi` when the imbalance exceeds a configured threshold.

## Requirements

- Debian-based target (Debian, Ubuntu 22.04 / 24.04)
- ASUS ROG Astral RTX 5090 / 5080 GPU with NVIDIA drivers and `nvidia-smi` available
- `python3-prometheus-client` and `python3-yaml` (installed by the role)
- A Vector instance that picks up scrape configs from `/etc/vector/` (the role drops a Prometheus scrape file there and notifies `vector-multi`)

## What the role does

1. Installs the Python runtime dependencies via apt.
2. Creates `/opt/astral-power-monitor/` and deploys the `astral_power_monitor` library plus the daemon script.
3. Templates `/etc/astral-power-monitor.yaml` from role variables.
4. Templates and enables the `astral-power-monitor.service` unit (runs as root for i2c and `nvidia-smi` power-limit access).
5. Drops `/etc/vector/astral-power-monitor.yaml` so Vector scrapes the daemon's `/metrics` endpoint.

## Role Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `astral_power_monitor_poll_interval` | `1.0` | Seconds between telemetry samples. |
| `astral_power_monitor_prometheus_port` | `9101` | TCP port the daemon listens on for Prometheus scrapes (bound to `0.0.0.0`). |
| `astral_power_monitor_fire_hazard_enabled` | `true` | Enable the fire-hazard detection and throttling logic. |
| `astral_power_monitor_fire_hazard_warning_stddev` | `0.1` | Per-pin current standard deviation that raises a warning. |
| `astral_power_monitor_fire_hazard_critical_stddev` | `0.5` | Per-pin current standard deviation that counts as a critical sample. |
| `astral_power_monitor_fire_hazard_pin_current_warning` | `8.0` | Per-pin current (A) that raises a warning. |
| `astral_power_monitor_fire_hazard_pin_current_critical` | `9.2` | Per-pin current (A) that counts as a critical sample. |
| `astral_power_monitor_fire_hazard_throttle_watts` | `250` | Power limit (W) applied via `nvidia-smi` once a critical condition is sustained. |
| `astral_power_monitor_fire_hazard_restore_on_clear` | `true` | Restore the original power limit once the condition clears. |
| `astral_power_monitor_fire_hazard_critical_count` | `3` | Number of consecutive critical samples required before the daemon throttles. |
| `astral_power_monitor_read_extra_rails` | `true` | Read auxiliary voltage rails in addition to the 12VHPWR pins. |
| `astral_power_monitor_log_level` | `"INFO"` | Python log level for the daemon (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

## Example Playbook

```yaml
- hosts: gpu_astral
  roles:
    - role: astral_power_monitor
      vars:
        astral_power_monitor_fire_hazard_throttle_watts: 300
        astral_power_monitor_fire_hazard_critical_count: 5
```

## Verification

After deployment:

```sh
systemctl status astral-power-monitor
curl -s http://127.0.0.1:9101/metrics | head
journalctl -u astral-power-monitor -n 50
```

## License

MIT
