# ethdevops.general.teleport_agent

This role installs and configures Teleport agent for secure access management.

## Requirements

- Teleport cluster accessible from target host
- `tctl` available on control node

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `teleport_agent_apps` | List of applications to expose | `[]` |
| `teleport_agent_desktops` | List of Windows desktops | `[]` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.general.teleport_agent
      vars:
        teleport_agent_apps:
          - name: grafana
            url: http://localhost:3000
```
