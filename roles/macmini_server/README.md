# ethdevops.general.macmini_server

This role configures Mac Mini systems for server mode operation.

## Requirements

- Mac Mini with Linux installed

## Role Variables

None

## Dependencies

None

## Example Playbook

```yaml
- hosts: macminis
  become: true
  roles:
    - role: ethdevops.general.macmini_server
```
