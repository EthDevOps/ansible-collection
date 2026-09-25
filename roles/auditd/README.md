# ethdevops.infrastructure.auditd

Installs [auditd](https://github.com/linux-audit/audit-project), deploys a
fleet-wide audit ruleset and ships `/var/log/audit/audit.log` to the central
VictoriaLogs sink through the existing `vector` setup (drop-in config at
`/etc/vector/auditd.yaml`).

## What is audited

| Key | Signal |
| --- | --- |
| `etc` | every write/attribute change anywhere under `/etc` |
| `sudoers`, `acct`, `pam`, `sshcfg` | dedicated keys on sudoers, account files, PAM and sshd config |
| `sshkeys` | every `~/.ssh` directory (root + all real user accounts) |
| `nbind` | `bind()` on AF_INET/AF_INET6; the kernel's `SOCKADDR` record carries the bound address (normalised to `bind_addr`/`bind_port` by the vector transform) |
| `rootexec` | every `execve` with `euid=0` (ENRICHED adds the command line) |
| `acctmgmt` | execution of useradd/usermod/groupadd/groupmod/chpasswd/passwd |
| `cron`, `systemd`, `root` | persistence locations (crontabs, systemd units, root home) |
| `modload`, `ptrace`, `time` | kernel module loads, process tracing, clock changes |
| `auditself` | the audit config and log directory themselves |
| `docks` | docker socket access (only when `auditd_watch_docker_sock` is true) |

## Shipping and alerting

The vector transform parses each audit line into flat fields (`audit_type`,
`key`, `name`, `comm`, `exe`, `proctitle`, `bind_addr`, `bind_port`, ...) and
tags the events with `log_type=audit` so the VictoriaLogs ingress can route
or filter them independently of the other log sources. The LogQL alerts that
consume these events live in
`ethquokkaops/monitoring-central` (Terraform `log_rules`).

## Immutability

With the default `auditd_immutable: true` the rules file contains `-e 2`,
which locks the ruleset in the kernel. While locked, changed rules only apply
after a reboot; the role deliberately does **not** restart auditd in that
case (it would fail to load the new ruleset and open a logging gap) and
prints a warning instead. Verify afterwards that the play's
"Verify all expected audit keys are active" task passes.

## Example Playbook

```yaml
- hosts: audited_hosts
  become: true
  roles:
    - role: ethdevops.infrastructure.auditd
```
