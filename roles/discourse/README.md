# ethdevops.general.discourse

This role deploys and configures a Discourse forum instance.

## Requirements

- Docker installed on target host

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `discourse_forum_domain` | Domain name for the forum | `""` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: forum
  become: true
  roles:
    - role: ethdevops.general.discourse
      vars:
        discourse_forum_domain: forum.example.com
```
