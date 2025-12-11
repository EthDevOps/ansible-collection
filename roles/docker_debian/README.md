# ethdevops.general.docker_debian

This role installs Docker on Debian-based systems using the official Docker repository.

## Requirements

- Debian or Ubuntu based system

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `docker_debian_users` | List of users to add to docker group | `[]` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: docker_hosts
  become: true
  roles:
    - role: ethdevops.general.docker_debian
      vars:
        docker_debian_users:
          - deploy
          - admin
```
