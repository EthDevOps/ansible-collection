# ethdevops.general.bootstrap

This role bootstraps new servers with basic configuration, packages, and user setup.

## Requirements

None

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `bootstrap_additional_users` | List of additional users to create | `[]` |
| `bootstrap_storage_optimized` | Enable storage optimizations | `false` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.general.bootstrap
      vars:
        bootstrap_additional_users:
          - name: deploy
            ssh_keys:
              - "ssh-ed25519 AAAA..."
```
