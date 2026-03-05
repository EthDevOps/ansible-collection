# ethdevops.infrastructure.wazuh_agent

This role installs and configures the Wazuh agent for host-based security monitoring. The agent enrolls automatically with the configured Wazuh manager using the APT repository method.

## Requirements

- Debian or Ubuntu target host
- Network connectivity from the target to the Wazuh manager on port 1514 (agent events) and 1515 (enrollment)

## Role Variables

Default variables are defined in [defaults/main.yml](defaults/main.yml)

| Variable | Description | Default |
|----------|-------------|---------|
| `wazuh_agent_manager_host` | Hostname or IP of the Wazuh manager | `wazuh.ethquokkaops.io` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.infrastructure.wazuh_agent
```

To override the manager host:

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.infrastructure.wazuh_agent
      vars:
        wazuh_agent_manager_host: "wazuh.example.com"
```

To disable the agent for specific hosts, set `wazuh_agent_enabled: false` in the relevant host or group vars.
