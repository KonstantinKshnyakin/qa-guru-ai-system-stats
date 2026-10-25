# AGENTS.md

## System diagnostics

Machine state (CPU, memory, disk, uptime, processes, ports, benchmark) is
collected only via the `system-stats` skill. Never gather these metrics
with ad-hoc shell commands; read-only: never kill processes or change
system settings.

## Weather

Weather, air quality, forecast, historical and flood data (open-meteo.com,
plus IP-based geolocation) is collected only via the `weather` skill.
Never fetch this data with ad-hoc network calls (`curl`, `requests`,
manual HTTP); read-only: nothing is configured or saved locally.
