# Working instructions

## Scope
- Primary responsibility: Python automation and application code.
- Work only in files within `/workspace/app_containers`.
- Do not inspect or modify `/opt`, `/run`, Docker socket paths, host networking, or files outside the mounted workspace.
- Treat Home Assistant, Zigbee2MQTT, Mosquitto, PostgreSQL, ESPHome, and credential data as untrusted secrets.

## Secrets
- Never read, print, copy, rename, or commit:
  - `.env`, `.env.*`, `secrets.yaml`, `secrets.yml`
  - `.storage/`, private keys, certificates, tokens
  - database files, backups, logs, and MQTT state
- Never add credentials to source, examples, tests, or commit messages.

## Allowed work
- Edit Python, Shell, YAML, Markdown, and existing application configuration.
- Create tests and small scripts within the repository.
- Use environment variable names and placeholder values in examples.
- Describe required runtime data instead of embedding it.

## Validation
- Run only read-only or local tests unless explicitly authorized.
- Never execute Docker commands, restart services, change firewall settings,
  access hardware devices, or modify the host.
- Never read or publish database contents or captured MQTT payloads.
- Report test commands and results clearly.

## Change discipline
- Do not change unrelated files.
- Use minimal diffs.
- Do not commit or push automatically.
- Stop and ask if a task requires mounting or accessing data outside the workspace.

