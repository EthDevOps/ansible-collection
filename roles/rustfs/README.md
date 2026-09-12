# ethdevops.general.rustfs

This role installs and configures [RustFS](https://docs.rustfs.com), an S3-compatible object storage server, as a systemd service.

## Requirements

- Debian/Ubuntu target host (uses `apt`)
- `x86_64` architecture

## Role Variables

Default variables are defined in [defaults/main.yml](defaults/main.yml)

| Variable | Description | Default |
|----------|-------------|---------|
| `rustfs_version` | RustFS server version. Installed to `/opt/rustfs/versions/<version>/`; changing it re-downloads, re-extracts and restarts the service | `"1.0.0-alpha.89"` |
| `rustfs_server_url` | Download URL for the server binary | GitHub release URL based on `rustfs_version` |
| `rustfs_client_version` | RustFS CLI (`rc`) version | `"0.1.3"` |
| `rustfs_client_url` | Download URL for the CLI client (`rc`) | GitHub release URL based on `rustfs_client_version` |
| `rustfs_port` | S3 API listen port | `9000` |
| `rustfs_console_port` | Web console listen port | `9001` |
| `rustfs_data_dir` | Path to the data/volumes directory | `"/data"` |
| `rustfs_domain` | Base domain for virtual-host-style bucket addressing (`RUSTFS_SERVER_DOMAINS`, e.g. `s3.example.com` so `bucket.s3.example.com` works); empty = path-style only | `""` |
| `rustfs_access_key` | Access key (override with a secret) | `"rustfsadmin"` |
| `rustfs_secret_key` | Secret key (override with a secret) | `"rustfsadmin"` |
| `rustfs_extra_env_vars` | Additional environment variables (dict) | `{}` |

## Dependencies

None

## What It Does

1. Installs required packages (`unzip`)
2. Creates a `rustfs` system user and necessary directories (`/opt/rustfs`, `/etc/rustfs`, `/var/log/rustfs`, data dir)
3. Downloads and extracts the RustFS server binary into a per-version directory
   (`/opt/rustfs/versions/<rustfs_version>/`), then points `/opt/rustfs/bin/rustfs` at it
   with a symlink. Downloads and extracts the CLI client
4. Symlinks `rustfs` and `rc` into `/usr/local/bin`
5. Deploys configuration to `/etc/rustfs/rustfs` and a systemd unit
6. Enables and starts the `rustfs` service
7. Waits for both the S3 API and web console ports to become available

## Upgrades and rollback

Both the download path and the install directory carry the version, so changing
`rustfs_version` always re-downloads and re-extracts rather than silently reusing a cached
archive. The `/opt/rustfs/bin/rustfs` symlink is what triggers the service restart, so it
fires on a version change and never on an unchanged re-run.

Previous versions stay under `/opt/rustfs/versions/`, so a rollback is just reverting
`rustfs_version` and re-running the role — no re-download. They are never pruned
automatically; remove old directories by hand when reclaiming disk.

> The service unit sets `Restart=always`, and the readiness checks run before the restart
> handler. A binary that crash-loops on startup will therefore still produce a successful
> play. After changing `rustfs_version`, confirm the result on the host — that
> `/proc/$(systemctl show -p MainPID --value rustfs)/exe` resolves into the expected version
> directory, and that `systemctl show rustfs -p NRestarts` is stable across a minute.

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
