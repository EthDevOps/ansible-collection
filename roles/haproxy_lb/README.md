# ethdevops.general.haproxy_lb

This role installs and configures HAProxy as a load balancer.

## Requirements

None

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

See defaults file for available configuration options.

## Dependencies

None

## Example Playbook

```yaml
- hosts: loadbalancers
  become: true
  roles:
    - role: ethdevops.general.haproxy_lb
```
