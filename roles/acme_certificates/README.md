# ethdevops.general.acme_certificates

This role manages ACME/Let's Encrypt certificates using Cloudflare DNS validation.

## Requirements

- Cloudflare account with API token for DNS management

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `acme_certificates_domains` | List of domains to get certificates for | `[]` |
| `acme_certificates_acme_email` | Email for ACME registration | `""` |
| `acme_certificates_cloudflare_api_token` | Cloudflare API token | `""` |

## Dependencies

None

## Example Playbook

```yaml
- hosts: webservers
  become: true
  roles:
    - role: ethdevops.general.acme_certificates
      vars:
        acme_certificates_domains:
          - example.com
          - www.example.com
        acme_certificates_acme_email: admin@example.com
        acme_certificates_cloudflare_api_token: "{{ vault_cloudflare_token }}"
```
