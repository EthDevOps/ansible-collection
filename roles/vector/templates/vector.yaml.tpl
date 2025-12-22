data_dir: "/var/lib/vector"
api:
  enabled: true

sources:
  metrics_node_exporter:
    type: prometheus_scrape
    endpoints:
      - http://127.0.0.1:9100/metrics

  logs_journal:
    type: journald

  logs_apt:
    type: file
    include:
      - /var/log/apt/history.log

{% if vector_docker_installed %}
  logs_docker:
    type: docker_logs
{% endif %}

transforms:
  metrics_with_labels:
    type: remap
    inputs: ["metrics_*"]
    source: |-
      .tags.hostname = "{{ inventory_hostname }}"
      .tags.environment = "{{ hostvars[inventory_hostname]['environment'] }}"
      .tags.project = "{{ project }}"
      .tags.tenant = "{{ tenants[0] }}"
  logs_with_labels:
    type: remap
    inputs: ["logs_*"]
    source: |-
      .tags.hostname = "{{ inventory_hostname }}"
      .tags.environment = "{{ hostvars[inventory_hostname]['environment'] }}"
      .tags.project = "{{ project }}"
      .tags.tenant = "{{ tenants[0] }}"

sinks:
  quokka_victoria:
    healthcheck:
      enabled: false
    type: prometheus_remote_write
    inputs: ["metrics_with_labels"{{ vector_extra_metrics }}]
    endpoint: https://{{ metrics_host }}/api/v1/write
    auth:
      strategy: basic
      user: "{% raw %}{{ with secret "{% endraw %}{{ vector_vault_secret_path }}{% raw %}" }}{{ .Data.data.{% endraw %}{{ vector_vault_user_field }}{% raw %} }}{{ end }}{% endraw %}"
      password: "{% raw %}{{ with secret "{% endraw %}{{ vector_vault_secret_path }}{% raw %}" }}{{ .Data.data.{% endraw %}{{ vector_vault_password_field }}{% raw %} }}{{ end }}{% endraw %}"

  quokka_vlogs:
    inputs: ["logs_with_labels"]
    type: "elasticsearch"
    endpoints: [ "https://{{logs_host}}/insert/elasticsearch/" ]
    mode: "bulk"
    api_version: "v8"
    healthcheck:
      enabled: false

    auth:
      strategy: basic
      user: "{% raw %}{{ with secret "{% endraw %}{{ vector_vault_secret_path }}{% raw %}" }}{{ .Data.data.{% endraw %}{{ vector_vault_user_field }}{% raw %} }}{{ end }}{% endraw %}"
      password: "{% raw %}{{ with secret "{% endraw %}{{ vector_vault_secret_path }}{% raw %}" }}{{ .Data.data.{% endraw %}{{ vector_vault_password_field }}{% raw %} }}{{ end }}{% endraw %}"
    query:
      _msg_field: "message"
      _time_field: "timestamp"
      _stream_fields: "host,container_name"

