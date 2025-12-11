# ethdevops.general.jvb

This role installs and configures Jitsi Videobridge (JVB) for video conferencing.

## Requirements

None

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `jvb_exporter_version` | Prometheus exporter version | See defaults |
| `jvb_jitsi_version` | Jitsi JVB version | See defaults |

## Dependencies

None

## Example Playbook

```yaml
- hosts: jvb_servers
  become: true
  roles:
    - role: ethdevops.general.jvb
```
