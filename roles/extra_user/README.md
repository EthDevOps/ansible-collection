# ethdevops.general.extra_user

This role creates additional system users with SSH key authentication.

## Requirements

None

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `extra_user_name` | Username to create | `""` |
| `extra_user_ssh_keys` | List of SSH public keys | `[]` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.general.extra_user
      vars:
        extra_user_name: deploy
        extra_user_ssh_keys:
          - "ssh-ed25519 AAAA... user@example.com"
```
