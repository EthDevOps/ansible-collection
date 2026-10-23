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
| `haproxy_lb_force_https` | `false` | If `true`, the `:80` frontend redirects HTTP→HTTPS (301) for any service that does not set `allow_http`. Leave off until you've observed which clients still need plain HTTP (see `haproxy_lb_access_log`). |
| `haproxy_lb_access_log` | `false` | If `true`, the `http`/`https` frontends log every request as JSON to the local Vector (UDP `127.0.0.1:5140`) instead of journald. Vector ships normal requests to the 1d log tier and errors (5xx, or a termination state other than `--`/`L*`) plus rate-limit events to the main tier. See [Access log](#access-log). |
| `haproxy_lb_rate_limit_targets` | `[]` | List of `{name, domain}`. Requests to these domains (on `:80` and `:443`) are tracked per source IP in the `Abuse` stick table and answered with `429` once a source exceeds `haproxy_lb_rate_limit_per_min` requests in the last 60 s, counted across all listed domains. Empty = no limiting. |
| `haproxy_lb_rate_limit_per_min` | `1500` | Per-source request threshold per 60 s for `haproxy_lb_rate_limit_targets`. |
| `haproxy_lb_rate_limit_exclude` | `[]` | Source IPs/CIDRs (written to `/etc/haproxy/allowlist.acl`) that are never rate limited, e.g. an event venue's NAT address. |

#### HTTP vs HTTPS frontends

The role emits two separate frontends:

- `frontend http` on `:80` — handles plain HTTP requests. When `haproxy_lb_force_https: true`, routes only services with `allow_http: true` and 301s everything else to HTTPS. When `false`, routes all services on HTTP too (default during discovery).
- `frontend https` on `:443` — handles TLS-terminated requests with HSTS and (optionally) HTTP/3.

Per-service opt-out from the HTTPS redirect:

- **Static sites**: set `allow_http: true` on the site.
- **K8s HTTP services**: set annotation `ethquokkaops.io/allow-http: "true"`.
- **Domain-group services**: set `custom_fields.allow_http: "true"`.

A service with `allow_http` set is served on both HTTP and HTTPS. Other services are only reachable over HTTPS once `haproxy_lb_force_https` is enabled.

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

Server IPs are resolved via `lb_hostvars[server]["primary_ip4"]`. Entries in `nodes` that are not in `lb_hostvars` are used as-is, so a literal IP works (e.g. `- 10.0.0.5`).

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
    allow_http: true              # Optional, also serve this site on plain HTTP (exempt from haproxy_lb_force_https redirect)
    health_check:                 # Optional, layer 7 health check (default is a bare TCP connect)
      path: /healthz              #   Required when health_check is set
      method: GET                 #   Optional, default GET
      host: myapp.example.com     #   Optional, Host header to send with the check
      expect_status: "200"        #   Optional, default "200". Accepts a list or range, e.g. "200,429"
```

#### Layer 7 health checks

By default a backend server is checked with a TCP (plus SSL, when `sslbackend`
is set) connect. That marks the server up as soon as the port is open, which is
wrong for applications that accept connections before they can serve — they
receive traffic and return errors. Set `health_check` to check an actual
endpoint instead:

```yaml
  tyrell:
    domains:
      - tyrell.example.com
    cluster: openbao-production
    sslbackend: true
    health_check:
      path: /v1/sys/health?standbyok=true
      expect_status: "200"
```

Omitting `health_check` leaves the previous TCP-only behaviour unchanged.

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
| `ethquokkaops.io/expose-public` | Required. `"true"` enables HTTP exposure; any other value (or absent) means the service is not routed |
| `ethquokkaops.io/domain` | Required (unless using `domain-port-map`). Comma-separated list of domains |
| `ethquokkaops.io/domain-port-map` | Optional. Map different domains to different service ports (see below) |
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
| `ethquokkaops.io/allow-http` | Optional. `"true"` exempts the service from the global HTTPS redirect (`haproxy_lb_force_https`) and routes plain HTTP requests to the same backend. |
| `ethquokkaops.io/dontlog-normal` | Optional. `"true"` logs only responses with status ≥ 500 for this service when `haproxy_lb_access_log` is on. Set it on log and metrics ingest endpoints, whose traffic would otherwise feed back into the access log. |
| `ethquokkaops.io/deny-paths` | Optional. Comma-separated public path prefixes rejected with a 403 at the edge (matched with `path_beg` after duplicate slashes are merged, before any `path` rewriting). Example: `"/api/auth/login"` |

**Backend name format:** `{cluster}_{namespace}_{servicename}` (e.g., `prod_default_myservice`)

#### Multi-Port Domain Mapping

Use `ethquokkaops.io/domain-port-map` to route different domains to different ports on the same service. This is useful for services that expose multiple endpoints (e.g., metrics, traces, API) on different ports.

**Format:** `domain1:portname1,domain2:portname2`

**Example:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: tempo
  namespace: monitoring
  annotations:
    ethquokkaops.io/expose-public: "true"
    ethquokkaops.io/domain: "tempo.example.com"  # Ignored when domain-port-map is present
    ethquokkaops.io/domain-port-map: "tempo-traces.example.com:tempo-otlp-http,tempo-metrics.example.com:tempo-prom-metrics"
spec:
  type: LoadBalancer
  ports:
    - name: tempo-otlp-http
      port: 4318
    - name: tempo-prom-metrics
      port: 3200
```

This generates:
- `tempo-traces.example.com` → backend on port 4318
- `tempo-metrics.example.com` → backend on port 3200

**Backend name format with domain-port-map:** `{cluster}_{namespace}_{servicename}_{portname}` (e.g., `prod_monitoring_tempo_tempo_otlp_http`)

### 3. Kubernetes TCP Services

TCP passthrough for Kubernetes services. Configured via annotations on the same `haproxy_lb_k8s_services` list.

#### Supported Annotations (TCP)

| Annotation | Description |
|------------|-------------|
| `ethquokkaops.io/expose-tcp` | Required. Enables TCP exposure |
| `ethquokkaops.io/expose-on-port` | Required. External port to listen on |
| `ethquokkaops.io/service-port` | Optional. Backend port (defaults to first service port) |
| `ethquokkaops.io/max-conn` | Optional. Max connections per server (default: 30) |
| `ethquokkaops.io/balance-group` | Optional. Collapses multiple services into a single backend with N server lines. Used when one logical LB endpoint needs to load-balance across multiple per-pod LB Services (e.g. StatefulSet pods that hold per-pod local state and require sticky client routing). |
| `ethquokkaops.io/balance` | Optional. HAProxy `balance` algorithm for the backend (e.g. `roundrobin`, `source`, `leastconn`). Defaults to `roundrobin`. Only consulted when `balance-group` is set; ungrouped backends always use `roundrobin`. |

**Backend name format:**
- Without `balance-group`: `tcp_{cluster}_{namespace}_{servicename}` (e.g. `tcp_prod_default_postgres`)
- With `balance-group`: `tcp_{cluster}_{group}` (e.g. `tcp_colo-k8s-mgmt_wazuh-worker-1514`). All grouped services must share the same `expose-on-port`; the first service's `max-conn` and `balance` annotations apply to the group.

##### Example: pod-sticky agent traffic (Wazuh)

Wazuh worker nodes keep per-agent state locally and do not synchronize it across the cluster, so agents must be sticky to one worker. Expose each StatefulSet pod via its own `LoadBalancer` Service (selector pinned to `statefulset.kubernetes.io/pod-name`), then collapse them into one HAProxy backend with `balance source` so each agent IP hashes deterministically to a specific worker:

```yaml
# Service for wazuh-manager-worker-0
metadata:
  annotations:
    ethquokkaops.io/expose-tcp: "true"
    ethquokkaops.io/expose-on-port: "1514"
    ethquokkaops.io/max-conn: "500"
    ethquokkaops.io/balance-group: "wazuh-worker-1514"
    ethquokkaops.io/balance: "source"
spec:
  selector:
    statefulset.kubernetes.io/pod-name: wazuh-manager-worker-0
# Service for wazuh-manager-worker-1: same annotations, selector ...worker-1.
```

Produces:

```
frontend fe_colo-k8s-mgmt_wazuh-worker-1514
    bind *:1514
    bind [::]:1514 v6only
    mode tcp
    option tcplog
    default_backend tcp_colo-k8s-mgmt_wazuh-worker-1514

backend tcp_colo-k8s-mgmt_wazuh-worker-1514
    mode tcp
    balance source

    default-server check maxconn 500 fall 3 rise 2
    server lb_wazuh-manager-worker-0 <pod-0 LB IP>:1514
    server lb_wazuh-manager-worker-1 <pod-1 LB IP>:1514
```

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
          allow_http: "true"            # Optional, exempt from haproxy_lb_force_https redirect
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

### 6. Warpgate-fronted Services

HTTP services published through [Warpgate](https://github.com/warp-tech/warpgate) can be reached through HAProxy: user -> haproxy -> warpgate -> service. Setting `haproxy_lb_warpgate_host` creates a single `warpgate` backend, and every discovered domain below is routed to it.

```yaml
haproxy_lb_warpgate_host: warpgate.example.org   # empty (default) = disabled
haproxy_lb_warpgate_port: 443
```

Services are selected by:

- **K8s**: `ethquokkaops.io/warpgate-expose: "web"` together with `ethquokkaops.io/domain` (comma-separated). `ethquokkaops.io/allow-http: "true"` is respected.
- **NetBox** (`lb_hostvars`): service `custom_fields.expose_mode: internal` together with a non-empty `expose_domain` (comma-separated). `custom_fields.allow_http: "true"` is respected.

HAProxy connects to Warpgate over HTTPS and, unless the gate domain below is set, passes the original Host header and SNI through unchanged. Warpgate's certificate won't match the requested host, so the backend uses `ssl verify none`. Warpgate itself chooses which service to forward to. Like all HTTP routing, this only applies when `haproxy_lb_sites` is non-empty.

**Real domains (`haproxy_lb_warpgate_gate_domain`).** Warpgate drops a logged-in session whose Host is not its `external_host` or a subdomain of it, so a target served on its own domain loops back to the login page. Set the gate domain, and K8s services get rewritten:

```yaml
haproxy_lb_warpgate_gate_domain: eu.gate.ethdevops.io   # empty (default) = Host passed through
```

- **Requests:** Host (and therefore SNI) becomes `<name>.<gate domain>`. `<name>` is `ethquokkaops.io/warpgate-name`, else `<namespace>-<service>`, so the Warpgate target's `external_host` must be that name.
- **SSO exception:** `/@warpgate/api/sso/` keeps the real Host. The Google return URL and the session cookie then land on the domain the browser uses. This needs `return_url_domain: host_header` on the Warpgate SSO provider.
- **Responses:** the session cookie loses `Domain=.<gate domain>`, so it stays host-only on the real domain. `Location` URLs on the gate domain are mapped back to the requested host.

NetBox services are not rewritten.

**Backend name format:** `warpgate`

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
| K8s HTTP services (multi-port) | `{cluster}_{namespace}_{service}_{portname}` | `prod_monitoring_tempo_tempo_otlp_http` |
| K8s TCP services | `tcp_{cluster}_{namespace}_{service}` | `tcp_prod_default_postgres` |
| Domain groups | Domain name | `app.example.com` |
| Warpgate | `warpgate` | `warpgate` |

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
- **Access log:** see [Access log](#access-log).
- **Rate limiting:** a source crossing the limit logs `rate-limit enter src=… host=… rate=…/60s` once; its first request back under the limit logs `rate-limit exit …`. A source that just stops sending logs no exit — its `Abuse` entry silently expires after 30 min idle. Rejected requests: `haproxy_backend_http_responses_total{proxy="rate_limited",code="4xx"}`. Currently limited sources: `show table Abuse data.gpt0 gt 0` on the admin socket. With `haproxy_lb_access_log` on, these lines are JSON with `rl_event`, `src`, `req_host` and `rl_rate` fields instead.

### Access log

With `haproxy_lb_access_log: true` every HTTP(S) request is logged as one JSON line (fields `src`, `req_host`, `fe`, `be`, `srv`, `method`, `path`, `query`, `status`, `term`, `Tt`/`Tr`/`Tw`/`Tc`, `bytes_out`, `bytes_in`, `retries`, `tls`) over UDP to the Vector source in `files/vector.yaml`. Vector tags normal requests `log_tier=short`, which the `vector` role's tier routing sends to the 1d tier; errors and rate-limit events stay in the main tier. TCP frontends keep logging errors to journald.

Example (requests per source over the last hour):

```
_time:1h fe:https | stats by (src) count() hits | sort by (hits desc) | limit 20
```

### Security

- HSTS enabled with 2-year max-age
- TLS 1.2+ only with modern cipher suites
- HTTP/2 and HTTP/1.1 ALPN support
- Optional per-source request-rate limit for selected domains (`haproxy_lb_rate_limit_targets`)

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
