# AGENTS.md

## System diagnostics tool

For any request asking to check/report the machine's state (CPU load, memory,
disk, uptime, top processes, listening ports, benchmark), use the read-only
tool `tools/system-stats.py`. Do NOT gather these metrics with ad-hoc shell
commands (`top`, `vm_stat`, `df`, `lsof`, ...) — always go through the tool.

### How to invoke

Run from the project root. Arguments are passed as JSON via the `TOOL_ARGS`
environment variable; the result is printed to stdout as JSON:

```bash
TOOL_ARGS='{"section":"load,mem,disk"}' python3 tools/system-stats.py
```

### Sections

- `load` — load average (1/5/15 min) and CPU core count
- `mem` — total / used / available RAM in bytes (macOS and Linux)
- `disk` — `/` usage, including `used_pct`
- `uptime` — system uptime
- `top` — top processes by CPU (optional arg `top_n`, 1..100, default 5)
- `ports` — listening TCP ports
- `bench` — SHA-256 throughput benchmark (optional arg `mb`, 1..1024, default 64)
- `all` — all sections (cannot be combined with others)

Multiple sections can be combined with a comma, e.g. `"section":"load,mem,disk"`.

### Default report flow

For a generic "check the machine" request:

1. Run the tool with `section` = `load,mem,disk`.
2. Compare `loadavg_5m` with `cpu_count`.
3. Flag RAM when available is below ~10% of total; flag disk when
   `used_pct` is above 90%.
4. Answer with one line per area (load / memory / disk). If a section
   contains `"error"`, report that area as "недоступно".

Run `ports` and `bench` only when explicitly asked — they are not part of
the default report.

### Constraints

- Read-only: never kill processes or change system settings.
- A section returning `{"error": ...}` or invalid-argument errors means the
  measurement is unavailable — report it, don't retry with other commands.
