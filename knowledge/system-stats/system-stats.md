# system-stats usage

Run from the project root; args go as JSON in `TOOL_ARGS`, result prints
to stdout as JSON:

```bash
TOOL_ARGS='{"section":"load,mem,disk"}' python3 tools/system-stats/system-stats.py
```

## Sections

- `load` — load average (1/5/15 min) and CPU core count
- `mem` — total / used / available RAM in bytes (macOS and Linux)
- `disk` — `/` usage, including `used_pct`
- `uptime` — system uptime
- `top` — top processes by CPU (optional arg `top_n`, 1..100, default 5)
- `ports` — listening TCP ports
- `bench` — SHA-256 throughput benchmark (optional arg `mb`, 1..1024, default 64)
- `all` — all sections (cannot be combined with others)

Combine sections with a comma: `"section":"load,mem,disk"`.

## Default report flow

For a generic "check the machine" request:

1. Run with `section` = `load,mem,disk`.
2. Compare `loadavg_5m` with `cpu_count`.
3. Flag RAM when available is below ~10% of total; flag disk when
   `used_pct` is above 90%.
4. Answer with one line per area (load / memory / disk). If a section
   contains `"error"`, report that area as "недоступно".

Run `ports` and `bench` only when explicitly asked — they are not part of
the default report.

## Errors

- A section returning `{"error": ...}` or invalid-argument errors means the
  measurement is unavailable — report it, don't retry with other commands.
