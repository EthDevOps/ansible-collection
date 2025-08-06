# Ansible Collection - ethereum.quokkaops

General Ansible roles from EF DevOps for infrastructure management, monitoring, and security.

## Installation

### Using GitHub Releases (Recommended)

Install a specific version from GitHub releases:

```bash
ansible-galaxy collection install https://github.com/ethereum-foundation/ansible-collection/releases/download/v1.2.0/ethereum-quokkaops-1.2.0.tar.gz
```

### Using requirements.yml

Add to your `requirements.yml`:

```yaml
collections:
  # Pin to a specific version
  - name: https://github.com/ethereum-foundation/ansible-collection/releases/download/v1.2.0/ethereum-quokkaops-1.2.0.tar.gz
    type: url
```

Then install with:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Version Management

This collection follows [semantic versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

### Staying Updated

For downstream repositories, you can use version constraints in your `requirements.yml`:

```yaml
collections:
  # Stay within major version 1.x (recommended)
  - name: ethereum.quokkaops
    version: ">=1.0.0,<2.0.0"
    
  # Or stay within minor version 1.2.x
  - name: ethereum.quokkaops
    version: ">=1.2.0,<1.3.0"
```

### Automated Updates

To automatically update your collection dependency to the latest version within constraints, run:

```bash
ansible-galaxy collection install -r requirements.yml --upgrade
```

## Available Roles

- **acme-certificates**: ACME certificate management
- **bootstrap**: System bootstrapping and basic configuration
- **discourse**: Discourse forum deployment
- **docker_debian**: Docker installation on Debian systems
- **extra-user**: Additional user management
- **grafana-agent**: Grafana agent deployment and configuration
- **haproxy-lb**: HAProxy load balancer configuration
- **jvb**: Jitsi Video Bridge setup
- **k3s**: Lightweight Kubernetes distribution
- **macmini-server**: Mac Mini server configuration
- **opnsense_nat**: OPNsense NAT configuration
- **teleport-agent**: Teleport agent setup
- **vector**: Vector log aggregation
- **vrrp**: VRRP/keepalived configuration

## Development

### Releasing

Use the automated release script:

```bash
# Increment patch version (1.0.0 -> 1.0.1)
./scripts/release.sh patch

# Increment minor version (1.0.1 -> 1.1.0)
./scripts/release.sh minor

# Increment major version (1.1.0 -> 2.0.0)
./scripts/release.sh major

# Set specific version
./scripts/release.sh 1.2.3
```

The script will:
1. Validate the current git state (clean working directory)
2. Update the version in `galaxy.yml`
3. Commit the version change
4. Create and push the version tag
5. Trigger GitHub Actions to build and publish the release

#### Manual Process

If you prefer to do it manually:
1. Update version in `galaxy.yml`
2. Create and push a git tag:
   ```bash
   git add galaxy.yml
   git commit -m "Bump version to 1.2.0"
   git tag v1.2.0
   git push origin main v1.2.0
   ```

### CI/CD

- **CI**: Runs on every push/PR with linting and build tests
- **Release**: Triggered on version tags, builds and publishes collection artifacts
