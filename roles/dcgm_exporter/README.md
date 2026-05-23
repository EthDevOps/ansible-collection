# DCGM Exporter Role

Deploys the NVIDIA DCGM exporter (`datacenter-gpu-manager-exporter`) as a systemd service on hosts with NVIDIA GPUs. The exporter exposes per-GPU health, utilization, memory, power, temperature, and profiling metrics for Prometheus on TCP/9400.

## What the role does

1. Installs NVIDIA's CUDA apt keyring (`cuda-keyring` deb) to enable the NVIDIA developer apt repository.
2. Installs `datacenter-gpu-manager-4-cuda12` (DCGM hostengine + libdcgm) and `datacenter-gpu-manager-exporter` from NVIDIA's repo.
3. Enables and starts `nvidia-dcgm.service` (the hostengine the exporter talks to).
4. Drops a systemd override at `/etc/systemd/system/nvidia-dcgm-exporter.service.d/override.conf` that pins the listen address, collectors file, and collect interval from role variables.
5. Enables and starts `nvidia-dcgm-exporter.service`.
6. Drops `/etc/vector/dcgm-exporter.yaml` so Vector scrapes the exporter's `/metrics` endpoint, and notifies `vector-multi` to restart.

## Requirements

- Debian 12 or Ubuntu 22.04 / 24.04
- NVIDIA driver already installed (the exporter relies on it via DCGM)
- A Vector instance that picks up scrape configs from `/etc/vector/` (the role notifies `vector-multi`)

## Role Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `dcgm_exporter_package_version` | `4.8.2-1` | apt-pinned version for `datacenter-gpu-manager-exporter`. |
| `dcgm_exporter_manager_package` | `datacenter-gpu-manager-4-cuda12` | DCGM hostengine package (use `-4-core` if CUDA 12 libs are not desired). |
| `dcgm_exporter_manager_version` | `1:4.5.3-1` | apt-pinned version for the DCGM hostengine package (NVIDIA ships this package with epoch `1:` — include it). |
| `dcgm_exporter_listen_address` | `0.0.0.0:9400` | `--address` flag for the exporter. |
| `dcgm_exporter_prometheus_port` | `9400` | Port Vector scrapes (should match the port in `dcgm_exporter_listen_address`). |
| `dcgm_exporter_collectors_file` | `/etc/dcgm-exporter/default-counters.csv` | `--collectors` CSV file shipped by the deb. Other choices: `dcp-metrics-included.csv`, `1.x-compatibility-metrics.csv`. |
| `dcgm_exporter_collect_interval_ms` | `30000` | `--collect-interval` in milliseconds. |
| `dcgm_exporter_extra_args` | `[]` | Extra CLI flags appended to the ExecStart line. |
| `dcgm_exporter_cuda_keyring_version` | `1.1-1` | Version of NVIDIA's `cuda-keyring` deb. |

## Example Playbook

```yaml
- hosts: gpu_servers
  roles:
    - role: dcgm_exporter
      vars:
        dcgm_exporter_collect_interval_ms: 15000
        dcgm_exporter_collectors_file: /etc/dcgm-exporter/dcp-metrics-included.csv
```

## Verification

```sh
systemctl status nvidia-dcgm nvidia-dcgm-exporter
curl -s http://127.0.0.1:9400/metrics | head
journalctl -u nvidia-dcgm-exporter -n 50
```

## License

MIT
