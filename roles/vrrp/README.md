# ethdevops.general.vrrp

This role configures VRRP (Virtual Router Redundancy Protocol) using keepalived for high availability.

## Requirements

None

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `vrrp_shared_ip` | Virtual IP address | `192.168.200.10` |
| `vrrp_secret` | VRRP authentication secret | See defaults |
| `vrrp_group` | VRRP group ID | `51` |
| `vrrp_role` | Role (master/backup) | `master` |
| `vrrp_priority` | VRRP priority | `100` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: ha_cluster
  become: true
  roles:
    - role: ethdevops.general.vrrp
      vars:
        vrrp_shared_ip: 10.0.0.100
        vrrp_secret: "{{ vault_vrrp_secret }}"
```
