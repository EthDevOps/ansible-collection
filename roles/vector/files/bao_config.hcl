template {
  source      = "/etc/openbao-agent/templates.d/vector.yaml.tpl"
  destination = "/etc/vector/vector.yaml"
  perms       = "0640"
  group       = "vector"
}
