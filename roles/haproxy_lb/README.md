# ethdevops.general.haproxy_lb

This role installs and configures HAProxy as a load balancer with support for multiple backend types, including static sites, Kubernetes services, TCP tunnels, and domain-based service groups.

## Requirements

- HAProxy 2.x or later
- SSL certificates in `/etc/certificates/` (managed separately)

## Role Variables

Default variables are defined in [defaults/main.yaml](defaults/main.yaml).

### General Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `haproxy_lb_sites_insecure` | `false` | If `true`, disables HTTPS binding on port 443 |
| `haproxy_lb_stats_user` | `user` | Username for HAProxy stats page |
| `haproxy_lb_stats_password` | `somepassword` | Password for HAProxy stats page |

### Cluster Definitions

Clusters define groups of backend servers that can be referenced by sites and tunnels.

```yaml
haproxy_lb_clusters:
  webservers:
    defaultPort: 8080
    # Option 1: Explicit node list
    nodes:
      - server1
      - server2
    # Option 2: Single Ansible group
    nodeGroup: web_servers
    # Option 3: Intersection of multiple groups
    nodeGroups:
      - production
      - web_tier
```

Server IPs are resolved via `lb_hostvars[server]["primary_ip4"]`.

---

## Backend Types

### 1. Static Sites (`haproxy_lb_sites`)

HTTP/HTTPS backends routing to server clusters. Sites with `path` defined are processed first (more specific routes).

```yaml
haproxy_lb_sites:
  myapp:
    domains:
      - myapp.example.com
      - www.myapp.example.com
    cluster: webservers
    port: 8080                    # Optional, overrides cluster defaultPort
    path: /api                    # Optional, path-based routing
    auth: admin_users             # Optional, require basic auth (references haproxy_lb_auth group)
    set_path: /v2%[path]          # Optional, rewrite request path
    use_cache: "true"             # Optional, enable response caching
    use_sticky: true              # Optional, enable sticky sessions via cookie
    sslbackend: true              # Optional, use HTTPS to backend servers
    http2: true                   # Optional, enable HTTP/2 to backend
    max_conn: 500                 # Optional, max connections per server (default: 500)
    balance_mode: backup          # Optional, "backup" uses first available server, others as backup
```

**Backend name format:** Site name (e.g., `myapp`)

### 2. Kubernetes HTTP Services (`haproxy_lb_k8s_services`)

Automatically discovers and routes to Kubernetes services based on annotations. Services with `ethquokkaops.io/path` annotation are processed first.

```yaml
haproxy_lb_k8s_services:
  - item: prod                    # Cluster identifier
    resources:                    # List of K8s Service resources (typically from k8s lookup)
      - metadata:
          name: myservice
          namespace: default
          annotations:
            ethquokkaops.io/expose-public: "true"
            ethquokkaops.io/domain: "app.example.com, api.example.com"
        spec:
          ports:
            - port: 80
        status:
          loadBalancer:
            ingress:
              - ip: 10.0.0.100
```

#### Supported Annotations (HTTP)

| Annotation | Description |
|------------|-------------|
| `ethquokkaops.io/expose-public` | Required. Enables HTTP exposure |
| `ethquokkaops.io/domain` | Required. Comma-separated list of domains |
| `ethquokkaops.io/path` | Optional. Comma-separated path prefixes for routing |
| `ethquokkaops.io/match-exact` | Optional. Use exact host matching instead of domain suffix |
| `ethquokkaops.io/allow-subdomains` | Optional. Also match subdomains (e.g., `*.example.com`) |
| `ethquokkaops.io/auth-group` | Optional. Require basic auth from specified group |
| `ethquokkaops.io/internal-only` | Optional. Restrict to internal IPs (10.128.0.0/9) |
| `ethquokkaops.io/use_cache` | Optional. Enable response caching (`"true"`) |
| `ethquokkaops.io/sticky` | Optional. Enable sticky sessions (`"true"`) |
| `ethquokkaops.io/ssl-backend` | Optional. Use HTTPS to backend |
| `ethquokkaops.io/http2-backend` | Optional. Enable HTTP/2 to backend |
| `ethquokkaops.io/max-conn` | Optional. Max connections per server (default: 500) |

**Backend name format:** `{cluster}_{namespace}_{servicename}` (e.g., `prod_default_myservice`)

### 3. Kubernetes TCP Services

TCP passthrough for Kubernetes services. Configured via annotations on the same `haproxy_lb_k8s_services` list.

#### Supported Annotations (TCP)

| Annotation | Description |
|------------|-------------|
| `ethquokkaops.io/expose-tcp` | Required. Enables TCP exposure |
| `ethquokkaops.io/expose-on-port` | Required. External port to listen on |
| `ethquokkaops.io/service-port` | Optional. Backend port (defaults to first service port) |
| `ethquokkaops.io/max-conn` | Optional. Max connections per server (default: 30) |

**Backend name format:** `tcp_{cluster}_{namespace}_{servicename}` (e.g., `tcp_prod_default_postgres`)

### 4. Domain Groups (via `lb_hostvars`)

Services defined in host variables that are grouped by domain for load balancing. Useful for distributing traffic across multiple hosts running the same service.

Services are discovered from `lb_hostvars[host].services` where `custom_fields.expose_mode == "l7"`.

```yaml
# In host_vars or group_vars
lb_hostvars:
  server1:
    primary_ip4: 10.0.0.1
    services:
      - name: webapp
        ports:
          - 8080
        custom_fields:
          expose_mode: l7
          expose_domain: "app.example.com"
          expose_auth: admin_users      # Optional, basic auth group
          internal_only: "true"         # Optional, restrict to internal IPs
          balance_mode: backup          # Optional, primary/backup mode
```

Multiple hosts with services on the same domain are automatically grouped into a single backend with round-robin load balancing.

**Backend name format:** Domain name (e.g., `example.com`)

### 5. TCP Tunnels (`haproxy_lb_tunnels`)

Generic TCP proxying to backend clusters.

```yaml
haproxy_lb_tunnels:
  postgres:
    port: 5432                    # External listen port
    cluster: db_servers           # Reference to haproxy_lb_clusters
    cluster_port: 5432            # Port on backend servers
    maxconn: 500                  # Optional, max connections (default: 500)
```

**Backend name format:** Tunnel name (e.g., `postgres`)

---

## Redirects (`haproxy_lb_redirects`)

Domain and path-based redirects processed before backend routing.

```yaml
haproxy_lb_redirects:
  # Domain redirect with path preservation
  - src:
      - old.example.com
      - legacy.example.com
    target: new.example.com
    code: 301
    preserve_uri: true            # Append original path to target

  # Domain redirect with path-specific targets
  - src:
      - docs.example.com
    target: example.com
    code: 302
    paths:
      - path: /v1
        target: /docs/v1
      - path: /v2
        target: https://newdocs.example.com/v2

  # Regex path redirect (in default backend)
  - match: "^/old-path/(.*)"
    dest: "https://example.com/new-path/\\1"

  # Simple domain redirect (in default backend)
  - domain: legacy.example.com
    dest: https://example.com
```

---

## Authentication (`haproxy_lb_auth`)

Define user groups for HTTP basic authentication.

```yaml
haproxy_lb_auth:
  - group: admin_users
    users:
      - name: admin
        password: secretpassword
      - name: readonly
        password: anotherpassword
```

Passwords are automatically hashed using SHA-256. Reference these groups in site configurations or K8s annotations.

---

## Custom Backend Configuration (`haproxy_lb_backend_extra_config`)

Inject raw HAProxy configuration into any backend type. Useful for custom health checks, timeouts, or other HAProxy directives.

```yaml
haproxy_lb_backend_extra_config:
  # Static site backend (key = site name)
  myapp: |
    option httpchk GET /health
    http-check expect status 200
    timeout server 30000

  # K8s HTTP backend (key = cluster_namespace_servicename)
  prod_default_myservice: |
    retries 5
    timeout server 120000
    option httpchk GET /ready
    http-check expect status 200

  # K8s TCP backend (key = tcp_cluster_namespace_servicename)
  tcp_prod_default_postgres: |
    timeout connect 10000
    timeout server 3600000

  # Domain group backend (key = domain name)
  app.example.com: |
    option httpchk GET /status
    http-check expect string OK
```

### Key Formats by Backend Type

| Backend Type | Key Format | Example |
|--------------|------------|---------|
| Static sites | Site name | `myapp` |
| K8s HTTP services | `{cluster}_{namespace}_{service}` | `prod_default_myservice` |
| K8s TCP services | `tcp_{cluster}_{namespace}_{service}` | `tcp_prod_default_postgres` |
| Domain groups | Domain name | `app.example.com` |

---

## Built-in Features

### Caching

A global cache is configured with:
- Total size: 512 MB
- Max object size: 100 KB
- Max age: 10 minutes

Enable per-site with `use_cache: "true"` or via K8s annotation `ethquokkaops.io/use_cache: "true"`.

### Compression

All HTTP backends automatically compress responses for:
- `text/css`, `text/html`, `text/javascript`, `application/javascript`
- `text/plain`, `text/xml`, `application/json`

### WebSocket Support

All HTTP backends have a 2-hour tunnel timeout for WebSocket connections.

### Monitoring

- **Stats page:** `http://127.0.0.1:32700/` (requires auth)
- **Prometheus metrics:** `http://127.0.0.1:9142/metrics`

### Security

- HSTS enabled with 2-year max-age
- TLS 1.2+ only with modern cipher suites
- HTTP/2 and HTTP/1.1 ALPN support

---

## Dependencies

None

## Example Playbook

```yaml
- hosts: loadbalancers
  become: true
  vars:
    haproxy_lb_stats_password: "{{ vault_haproxy_stats_password }}"

    haproxy_lb_clusters:
      web:
        defaultPort: 8080
        nodeGroup: webservers
      db:
        nodes:
          - db1
          - db2

    haproxy_lb_sites:
      webapp:
        domains:
          - app.example.com
        cluster: web

      api:
        domains:
          - api.example.com
        cluster: web
        path: /v1

    haproxy_lb_tunnels:
      postgres:
        port: 5432
        cluster: db
        cluster_port: 5432

    haproxy_lb_auth:
      - group: admins
        users:
          - name: admin
            password: "{{ vault_admin_password }}"

    haproxy_lb_backend_extra_config:
      webapp: |
        option httpchk GET /health
        http-check expect status 200

  roles:
    - role: ethdevops.general.haproxy_lb
```

## License

MIT
