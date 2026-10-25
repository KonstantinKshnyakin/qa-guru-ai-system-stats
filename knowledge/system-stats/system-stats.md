# system-stats reference

Run from the project root; args go as JSON in `TOOL_ARGS`, result prints
to stdout as JSON:

```bash
TOOL_ARGS='{"section":"load,mem,disk"}' python3 tools/system-stats/system-stats.py
```

## Arguments

- `section` — a name or comma-separated list; default `load,mem,disk`.
- `top_n` — processes in `top`, 1..100, default 5.
- `mb` — megabytes hashed in `bench`, 1..1024, default 64.

## Sections

- `load` — load average (1/5/15 min) and CPU core count on macOS/Linux;
  on Windows (no load average concept) `cpu_percent` — instantaneous CPU
  utilization, 0..100 — and `cpu_count` instead
- `mem` — total / used / available RAM in bytes (macOS, Linux, Windows)
- `disk` — `/` usage, including `used_pct`
- `uptime` — system uptime
- `top` — top processes by CPU (`top_n`); `cpu_pct`/`mem_pct` on
  macOS/Linux, but on Windows `cpu_seconds` (cumulative CPU time, not a
  percentage) and `mem_pct`
- `ports` — listening TCP ports
- `bench` — SHA-256 throughput benchmark (`mb`)
- `all` — all sections; explicit only, cannot be combined with others

## Output and error format

- One requested section — its result prints unwrapped; several — an
  object keyed by section name.
- Invalid arguments — `{"error": "invalid arguments: ..."}`, exit 1.
- A failed collector — `"error"` inside its section's result, exit 0.
  Inspect the error. If the execution sandbox blocks system access,
  request permission through the environment's approval mechanism and
  rerun this same tool outside the sandbox. Never bypass a denied approval
  or collect metrics with alternative commands. If the approved run still
  fails, report the error; do not claim successful diagnostics.

## Interpretation

- macOS/Linux: compare `loadavg_5m` with `cpu_count`.
- Windows: flag `cpu_percent` above ~85%; there is no load-average
  equivalent, so do not compare it against `cpu_count`.
- Flag RAM when available is below ~10% of total; flag disk when
  `used_pct` is above 90%.
- On Windows, `ports` and `top` shell out to `netstat`/`tasklist` and
  `powershell` respectively; `top`'s `cpu_seconds` is cumulative CPU time
  since process start, not a percentage like on macOS/Linux.
