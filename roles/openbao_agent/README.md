# OpenBao Agent Role

Installs and configures the OpenBao agent on Debian-based systems with AppRole authentication.

## Requirements

- Debian-based target system (Debian, Ubuntu)
- OpenBao CLI (`bao`) installed on the Ansible control node
- Valid OpenBao token on the control node with permissions to:
  - Read role-id: `auth/<mount>/role/host-<hostname>/role-id`
  - Generate secret-id: `auth/<mount>/role/host-<hostname>/secret-id`

## Role Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `openbao_agent_server_addr` | `https://vault.example.com:8200` | OpenBao server address |
| `openbao_agent_approle_mount_path` | `approle` | AppRole auth mount path |
| `openbao_agent_wrap_ttl` | `120s` | TTL for wrapped secret-id |
| `openbao_agent_cache_enabled` | `false` | Enable token caching proxy |
| `openbao_agent_listener_address` | `127.0.0.1:8100` | Cache listener address |
| `openbao_agent_sink_path` | `/run/openbao-agent/token` | Path where agent writes token |
| `openbao_agent_templates` | `[]` | List of templates to render (in main config) |
| `openbao_agent_exit_after_auth` | `false` | Exit after obtaining token |

## AppRole Naming Convention

The role expects AppRoles to follow the naming pattern: `host-<inventory_hostname>`

For example, if your inventory hostname is `webserver01`, the role will authenticate using the AppRole `host-webserver01`.

## Configuration Directory Pattern

This role creates a modular configuration structure:

```
/etc/openbao-agent/
├── agent.hcl           # Main agent config (auto_auth, cache, listener)
├── conf.d/             # Drop-in directory for additional configs
│   └── *.hcl           # Other roles can add template configs here
├── templates.d/        # Directory for Consul-Template style templates
│   └── *.tpl           # Template source files
├── role-id             # AppRole role-id (managed by this role)
└── secret-id           # Wrapped secret-id (consumed on startup)
```

Other Ansible roles can drop template configuration files into `/etc/openbao-agent/conf.d/` and template source files into `/etc/openbao-agent/templates.d/`.

### Example: Adding templates from another role

In another role's tasks:

```yaml
- name: Deploy database secrets template source
  ansible.builtin.copy:
    content: |
      {{ '{{' }} with secret "database/creds/myapp" {{ '}}' }}
      DB_USER={{ '{{' }} .Data.username {{ '}}' }}
      DB_PASS={{ '{{' }} .Data.password {{ '}}' }}
      {{ '{{' }} end {{ '}}' }}
    dest: /etc/openbao-agent/templates.d/database.tpl
    owner: openbao
    group: openbao
    mode: "0640"
  notify: Restart openbao-agent

- name: Deploy database template config
  ansible.builtin.copy:
    content: |
      template {
        source      = "/etc/openbao-agent/templates.d/database.tpl"
        destination = "/etc/myapp/database.env"
        perms       = "0640"
        command     = "systemctl restart myapp"
      }
    dest: /etc/openbao-agent/conf.d/database.hcl
    owner: openbao
    group: openbao
    mode: "0640"
  notify: Restart openbao-agent
```

## Example Playbook

```yaml
- hosts: servers
  roles:
    - role: openbao_agent
      vars:
        openbao_agent_server_addr: "https://vault.example.com:8200"
        openbao_agent_approle_mount_path: "approle"
```

## Accessing Secrets

The primary method is through templating - the agent renders secrets directly to files that applications can read.

Alternatively, the agent writes its token to `/run/openbao-agent/token`. Applications can read this token to authenticate directly with OpenBao, or enable `openbao_agent_cache_enabled` to use a local API proxy.

## License

MIT
