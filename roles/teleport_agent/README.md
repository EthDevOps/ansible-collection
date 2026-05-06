# ethdevops.general.teleport_agent

This role installs and configures the Teleport agent using Managed Updates v2.
Installation goes through the cluster's `/scripts/install.sh` bootstrap, which
downloads the `teleport-update` binary from `cdn.teleport.dev` and registers a
local `teleport-update.timer`. The Debian/Ubuntu apt repository is no longer
used; the agent version is controlled cluster-side via the `autoupdate_version`
resource. Existing apt-managed hosts are converted in place on first run, and
the legacy repo files are removed.

## Requirements

- Teleport cluster accessible from target host (HTTPS to `{{ teleport_cluster }}:443`)
- `tctl` available on control node
- `curl` available on the target host

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `teleport_agent_apps` | List of applications to expose | `[]` |
| `teleport_agent_desktops` | List of Windows desktops | `[]` |
| `teleport_agent_update_group` | Managed Updates v2 group; matches a schedule in the cluster's `autoupdate_config` | `default` |
| `teleport_agent_enhanced_recording_enabled` | Enable SSH enhanced session recording (BPF). Requires a recent kernel; scope per-group rather than globally. | `false` |
| `teleport_agent_enhanced_recording_command_buffer_size` | BPF command event buffer size, in pages | `8` |
| `teleport_agent_enhanced_recording_network_buffer_size` | BPF network event buffer size, in pages | `8` |

`teleport_cluster` (proxy hostname) must be defined at the inventory level.
`teleport_version` is no longer consumed; remove it from inventory if you only
used it for this role.

## Dependencies

None

## Example Playbook

```yaml
- hosts: all
  become: true
  roles:
    - role: ethdevops.general.teleport_agent
      vars:
        teleport_agent_apps:
          - name: grafana
            url: http://localhost:3000
```
