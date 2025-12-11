# ethdevops.general.vector

This role installs and configures Vector for logs and metrics collection.

## Requirements

None

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `vector_extra_metrics` | Additional metrics configuration | `""` |
| `vector_install_nodexporter` | Install node_exporter | `true` |
| `vector_version` | Vector version to install | `"0.51.1-1"` |

## Dependencies

- `prometheus.prometheus.node_exporter` (optional, when `vector_install_nodexporter` is true)

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.general.vector
      vars:
        vector_install_nodexporter: true
```
