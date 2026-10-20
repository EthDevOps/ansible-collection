# frr_bgp

One FRR speaker per host on a routed L3 fabric: a switch pair that holds an SVI
(`.252` / `.253`) in every `/24` it routes and accepts speakers through one
`bgp listen range` per VLAN, with the VLAN's ASN as remote-as.

The speaker announces what the host owns (its host route, any VRRP VIP it
currently holds, whatever a local routing daemon such as Cilium hands over),
learns what every other speaker owns from the SVIs of its own VLAN and installs
those routes in the kernel. Hosts that talk to each other through the fabric
therefore use it in both directions; everything else stays on the default
gateway in both directions, which keeps a stateful firewall on that path
symmetric.

```yaml
- hosts: loadbalancers
  become: true
  vars:
    frr_bgp_local_asn: 64500
    frr_bgp_fabric_asn: 64501
    frr_bgp_fabric_password: "{{ lookup('community.hashi_vault.vault_kv2_get', 'network/bgp').secret.md5 }}"
    frr_bgp_announce_connected: ["192.0.2.10/32"]   # VRRP VIP
  roles:
    - role: ethdevops.infrastructure.frr_bgp
```

| Variable | Meaning |
|---|---|
| `frr_bgp_local_asn` | The VLAN's ASN (required) |
| `frr_bgp_fabric_asn` | The switches' ASN (required unless `frr_bgp_fabric_peers` is set) |
| `frr_bgp_fabric_svis` | SVI host parts and names (`.252` / `.253`); names only go into descriptions |
| `frr_bgp_fabric_peers` | Derived from the primary /24 and the two above unless set |
| `frr_bgp_router_id` | Defaults to the primary IP; hosts with a local speaker set another address |
| `frr_bgp_upstream_peers` | Announce-only peers (default gateway), cluster nodes only |
| `frr_bgp_local_speakers` | Daemons on this host that hand prefixes to FRR (Cilium) |
| `frr_bgp_announce_host_route` | Announce `<primary IP>/32` (default true) |
| `frr_bgp_announce_connected` | `/32`s announced while present on an interface (VRRP VIPs) |
| `frr_bgp_fabric_deny` | Extra prefixes never accepted from the fabric |
| `frr_bgp_wait_for_fabric` | Fail the play unless all fabric sessions establish (default true) |
| `frr_bgp_fabric_password` / `_upstream_` | TCP MD5 keys; the `frr.conf` diff is hidden when one is set |
| `frr_bgp_fabric_ttl_security` / `_upstream_` | GTSM, `ttl-security hops 1` (fabric default true, upstream false) |
| `frr_bgp_fabric_max_prefix` / `_upstream_` / `_local_speaker_` | Session shut above this many prefixes (2000 / 10 / 512) |
| `frr_bgp_bfd` | BFD on the fabric sessions, 300 ms × 3 (default true; UDP 3784 must be open from the SVIs) |
| `frr_bgp_exporter_version` / `_sha256` | Pinned `frr_exporter` release |

Rendered policy, in `/etc/frr/frr.conf`:

- `PL-ORIGIN` out to the fabric: host route, connected VIPs, local-speaker prefixes.
- `PL-UPSTREAM-OUT` out to upstreams: local-speaker prefixes only.
- `PL-FABRIC-IN` in from the fabric: everything except a default route and the host's own connected subnets.
- `RM-LOCAL-SPEAKER-IN`: accept the declared prefixes, next-hop rewritten to the host.
- `RM-BGP-TO-KERNEL` (zebra): local-speaker prefixes never reach the kernel.

The role also stops systemd-networkd from reaping zebra's routes
(`ManageForeignRoutes=no`) and ties `frr.service` to `systemd-networkd.service`
so a networkd restart re-installs the FIB.

Monitoring: `frr_exporter` on `127.0.0.1:9342`, scraped by Vector
(`/etc/vector/frr.yaml`, the `vector` role's `vector-multi` service).
