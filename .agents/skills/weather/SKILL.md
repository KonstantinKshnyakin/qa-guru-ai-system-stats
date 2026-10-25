---
name: weather
description: Look up current weather, short-term forecast and air quality via the read-only tools/weather/weather.py (open-meteo.com). Use when asked about weather, temperature, precipitation, air quality, or forecast for a city or location. Historical weather, seasonal forecast and flood risk are available on explicit request.
---

# weather

1. For a generic "what's the weather" request (with or without a named
   city) run the tool with `section` = `current` (also the tool's
   default). If no city/coordinates are given, the tool falls back to
   approximate IP-based geolocation itself — do not ask the user for a
   city first.
2. `forecast` — only when a specific future period is asked for
   ("tomorrow", "next week", etc).
3. `historical`, `seasonal`, `flood`, `air_quality` (detailed) — only on
   direct request of those diagnostics.
4. Interpret the report and answer with one short line per area asked
   about. Flag IP-based location as approximate (city/region, not exact).

Never build the HTTP requests yourself (no `curl`, no `requests`, no
ad-hoc Python) — always go through this tool, even for a single field.

Interface (arguments, sections, output and error format) and
interpretation rules: `knowledge/weather/weather.md`.
