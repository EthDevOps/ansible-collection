# ethdevops.general.grafana_agent

This role installs and configures Grafana Agent for metrics and logs collection.

## Requirements

None

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `grafana_agent_metrics_extra_targets` | Additional scrape targets | `[]` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.general.grafana_agent
      vars:
        grafana_agent_metrics_extra_targets:
          - job_name: custom_app
            targets:
              - localhost:9090
```
