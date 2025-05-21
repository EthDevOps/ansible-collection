# Ansible Role: OPNsense NAT

This role manages NAT (Network Address Translation) rules in OPNsense firewalls.

## Requirements

- Ansible 2.9 or higher
- Access to OPNsense firewall with administrative credentials

## Role Variables

### Required Variables

```yaml
opnsense_username: "admin"       # OPNsense admin username
opnsense_password: "secret"      # OPNsense admin password
```

The role will automatically:
1. Login to OPNsense using the provided credentials
2. Extract the PHPSESSID from the login response
3. Get the NAT page CSRF token using the session
4. Use these tokens for all NAT rule operations

### Optional Variables

```yaml
opnsense_host: "10.128.0.1"  # IP or hostname of your OPNsense firewall
opnsense_validate_certs: false  # Whether to validate SSL certificates
```

### NAT Rules Configuration

NAT rules are defined in the `opnsense_nat_rules` list. Each rule is a dictionary with the following parameters:

```yaml
opnsense_nat_rules:
  - interface: ["wan"]  # Interface list
    ipprotocol: "inet"  # IP protocol (inet or inet6)
    protocol: "udp"     # Protocol (tcp, udp, etc)
    src: "any"         # Source address
    src_port_start: "any"  # Source port start
    src_port_end: "any"    # Source port end
    destination: "212.99.218.67"  # Destination address
    dst_port_start: "32007"  # Destination port start
    dst_port_end: "32007"    # Destination port end
    target: "10.128.2.46"    # Target IP address
    local_port: "32007"      # Local port
    description: "test-iac2"  # Rule description
    nat_reflection: "default" # NAT reflection setting
    associated_rule_id: "add-associated"  # Associated filter rule
```

## Example Playbook

```yaml
- hosts: opnsense
  vars:
    opnsense_host: "10.128.0.1"
    opnsense_phpsessid: "945204430dd209f221a600d23183abbe"  # from browser session
    csrf_token: "sHEqCxDa7lwYfKJ-dMhk4A"                    # from form submission
    opnsense_nat_rules:
      - interface: ["wan"]
        protocol: "udp"
        destination: "212.99.218.67"
        dst_port_start: "32007"
        dst_port_end: "32007"
        target: "10.128.2.46"
        local_port: "32007"
        description: "Game Server NAT"
        after: "9"  # Optional: position where to insert the rule
  roles:
    - opnsense_nat
```

## License

MIT

## Author Information

Created in 2024
