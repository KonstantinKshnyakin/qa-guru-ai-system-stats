# AGENTS.md

## System diagnostics

For any request asking to check/report the machine's state (CPU load, memory,
disk, uptime, top processes, listening ports, benchmark), use the read-only
tool `tools/system-stats.py` — see the `system-stats` skill for usage.

Do NOT gather these metrics with ad-hoc shell commands (`top`, `vm_stat`,
`df`, `lsof`, ...) — always go through the tool. Read-only: never kill
processes or change system settings.
