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
| `bootstrap_default_locale` | System locale. Removes stale `LC_*` overrides from `/etc/default/locale` and `/etc/environment`, sets `LANG`, and (for locales other than `C`/`C.UTF-8`) installs the `locales` package and generates the locale via `locale-gen` | `C.UTF-8` |

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
