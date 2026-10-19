#!/usr/bin/env python3
"""system-stats tool: local system diagnostics as a JSON report.

Devin --extend-tools contract: args arrive as JSON in TOOL_ARGS, stdout is
the tool result. Read-only, stdlib only; every failure — bad input or a dead
collector — reports {"error": ...} as JSON on stdout.
"""

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

SYSTEM = platform.system()  # "Darwin" | "Linux"
DEFAULT_TOP_N = 5
MAX_TOP_N = 100
DEFAULT_BENCH_MB = 64
MAX_BENCH_MB = 1024
CMD_TIMEOUT = 10


def _run(cmd):
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=CMD_TIMEOUT, check=True
    ).stdout


def _section(fn):
    """Run a collector; on failure report the error inside the section."""
    try:
        return fn()
    except Exception as e:
        return {"error": str(e)}


def collect_load():
    l1, l5, l15 = os.getloadavg()
    return {
        "loadavg_1m": round(l1, 2),
        "loadavg_5m": round(l5, 2),
        "loadavg_15m": round(l15, 2),
        "cpu_count": os.cpu_count(),
    }


def _mem_darwin():
    total = int(_run(["sysctl", "-n", "hw.memsize"]).strip())
    out = _run(["vm_stat"])
    page_size = int(re.search(r"page size of (\d+) bytes", out).group(1))
    pages = {
        name: int(count)
        for name, count in re.findall(r"Pages ([\w ]+):\s+(\d+)\.", out)
    }

    def get(*names):
        return sum(pages.get(n, 0) for n in names) * page_size

    return {
        "total_bytes": total,
        "used_bytes": get("active", "wired", "wired down", "occupied by compressor"),
        "available_bytes": get("free", "inactive", "speculative"),
    }


def _mem_linux():
    info = {}
    for line in open("/proc/meminfo"):
        key, rest = line.split(":", 1)
        info[key] = int(rest.strip().split()[0]) * 1024  # kB -> bytes
    return {
        "total_bytes": info["MemTotal"],
        "used_bytes": info["MemTotal"] - info.get("MemAvailable", info["MemFree"]),
        "available_bytes": info.get("MemAvailable", info["MemFree"]),
    }


def collect_mem():
    if SYSTEM == "Darwin":
        return _mem_darwin()
    if SYSTEM == "Linux":
        return _mem_linux()
    return {"error": f"unsupported platform: {SYSTEM}"}


def collect_disk():
    usage = shutil.disk_usage("/")
    return {
        "path": "/",
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_pct": round(usage.used / usage.total * 100, 1),
    }


def _uptime_seconds():
    if SYSTEM == "Darwin":
        out = _run(["sysctl", "-n", "kern.boottime"])
        return time.time() - float(re.search(r"sec = (\d+)", out).group(1))
    if SYSTEM == "Linux":
        return float(open("/proc/uptime").read().split()[0])
    raise ValueError(f"unsupported platform: {SYSTEM}")


def collect_uptime():
    total = int(_uptime_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    return {
        "uptime_seconds": total,
        "uptime_human": f"{days}d {hours}h {rem // 60}m",
    }


def collect_top(top_n):
    if SYSTEM == "Darwin":
        cmd = ["ps", "-Ao", "pid=,pcpu=,pmem=,comm=", "-r"]
    elif SYSTEM == "Linux":
        cmd = ["ps", "-eo", "pid=,pcpu=,pmem=,comm=", "--sort=-pcpu"]
    else:
        return {"error": f"unsupported platform: {SYSTEM}"}
    out = _run(cmd)
    procs = []
    for line in out.splitlines()[:top_n]:
        pid, cpu, mem, comm = line.split(None, 3)
        procs.append(
            {"pid": int(pid), "cpu_pct": float(cpu), "mem_pct": float(mem), "cmd": comm.strip()}
        )
    return {"processes": procs}


def collect_ports():
    out = _run(["lsof", "+c", "0", "-nP", "-iTCP", "-sTCP:LISTEN"])
    seen = {}
    for line in out.splitlines()[1:]:
        parts = line.split()
        m = re.search(r":(\d+) \(LISTEN\)", line)
        if m:
            seen.setdefault((int(m.group(1)), parts[0]), None)
    return {
        "listening": [
            {"port": port, "process": cmd} for port, cmd in sorted(seen)
        ]
    }


def collect_bench(mb):
    block = os.urandom(1024 * 1024)
    start = time.perf_counter()
    h = hashlib.sha256()
    for _ in range(mb):
        h.update(block)
    elapsed = time.perf_counter() - start
    return {
        "mb_hashed": mb,
        "seconds": round(elapsed, 3),
        "mb_per_sec": round(mb / elapsed, 1),
        "algo": "sha256",
    }


SECTIONS = {
    "load": collect_load,
    "mem": collect_mem,
    "disk": collect_disk,
    "uptime": collect_uptime,
    "top": collect_top,
    "ports": collect_ports,
    "bench": collect_bench,
}


def _int_arg(args, name, default, lo, hi):
    v = args.get(name, default)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{name} must be an integer, got {v!r}")
    if not lo <= v <= hi:
        raise ValueError(f"{name} must be {lo}..{hi}, got {v}")
    return v


def main() -> int:
    try:
        args = json.loads(os.environ.get("TOOL_ARGS", "{}"))
        if not isinstance(args, dict):
            raise ValueError("TOOL_ARGS must be a JSON object")
        section = args.get("section", "all")
        if not isinstance(section, str):
            raise ValueError(f"section must be a string, got {section!r}")
        names = list(dict.fromkeys(s.strip() for s in section.split(",") if s.strip()))
        if not names:
            raise ValueError("section must not be empty")
        if "all" in names:
            if len(names) > 1:
                raise ValueError("'all' cannot be combined with other sections")
            names = list(SECTIONS)
        else:
            bad = sorted(set(names) - set(SECTIONS))
            if bad:
                raise ValueError(
                    f"unknown section(s): {', '.join(bad)} "
                    f"(valid: all, {', '.join(SECTIONS)})"
                )
        top_n = _int_arg(args, "top_n", DEFAULT_TOP_N, 1, MAX_TOP_N)
        mb = _int_arg(args, "mb", DEFAULT_BENCH_MB, 1, MAX_BENCH_MB)
    except (ValueError, TypeError) as e:
        print(json.dumps({"error": f"invalid arguments: {e}"}))
        return 1

    report = {}
    for name in names:
        fn = SECTIONS[name]
        if name == "top":
            report[name] = _section(lambda: fn(top_n))
        elif name == "bench":
            report[name] = _section(lambda: fn(mb))
        else:
            report[name] = _section(fn)

    print(json.dumps(report if len(report) > 1 else report[names[0]], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
