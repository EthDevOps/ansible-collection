# ethdevops.general.rustfs

This role installs and configures [RustFS](https://docs.rustfs.com), an S3-compatible object storage server, as a systemd service.

## Requirements

- Debian/Ubuntu target host (uses `apt`)
- `x86_64` architecture

## Role Variables

Default variables are defined in [defaults/main.yml](defaults/main.yml)

| Variable | Description | Default |
|----------|-------------|---------|
| `rustfs_version` | RustFS server version | `"1.0.0-alpha.83"` |
| `rustfs_server_url` | Download URL for the server binary | GitHub release URL based on `rustfs_version` |
| `rustfs_client_url` | Download URL for the CLI client (`rc`) | GitHub release URL (v0.1.3) |
| `rustfs_port` | S3 API listen port | `9000` |
| `rustfs_console_port` | Web console listen port | `9001` |
| `rustfs_data_dir` | Path to the data/volumes directory | `"/data"` |
| `rustfs_access_key` | Access key (override with a secret) | `"rustfsadmin"` |
| `rustfs_secret_key` | Secret key (override with a secret) | `"rustfsadmin"` |
| `rustfs_extra_env_vars` | Additional environment variables (dict) | `{}` |

## Dependencies

None

## What It Does

1. Installs required packages (`unzip`)
2. Creates a `rustfs` system user and necessary directories (`/opt/rustfs`, `/etc/rustfs`, `/var/log/rustfs`, data dir)
3. Downloads and extracts the RustFS server and CLI client binaries
4. Symlinks `rustfs` and `rc` into `/usr/local/bin`
5. Deploys configuration to `/etc/rustfs/rustfs` and a systemd unit
6. Enables and starts the `rustfs` service
7. Waits for both the S3 API and web console ports to become available

## Example Playbook

```yaml
- hosts: storage
  become: true
  roles:
    - role: ethdevops.general.rustfs
      vars:
        rustfs_access_key: "{{ vault_rustfs_access_key }}"
        rustfs_secret_key: "{{ vault_rustfs_secret_key }}"
        rustfs_data_dir: "/mnt/storage"
```
