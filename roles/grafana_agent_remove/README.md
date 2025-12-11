# ethdevops.general.grafana_agent_remove

This role removes Grafana Agent from systems.

## Requirements

None

## Role Variables

None

## Dependencies

None

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.general.grafana_agent_remove
```
