# weather reference

Run from the project root; args go as JSON in `TOOL_ARGS`, result prints
to stdout as JSON:

```bash
TOOL_ARGS='{"section":"current","city":"Paris"}' python3 tools/weather/weather.py
```

All data comes from the free, keyless open-meteo.com API family plus
`ip-api.com` for approximate IP geolocation. No network access other
than those documented hosts; no API keys; no state is written anywhere.

## Arguments

- `section` — a name or comma-separated list; default `current`.
- `city` — city/place name, optional. Passed to the Geocoding API
  (`language=ru`). Mutually exclusive with `lat`/`lon`.
- `lat`, `lon` — coordinates (WGS84), optional, must be given together.
  Mutually exclusive with `city`.
- If none of `city`/`lat`/`lon` are given, location is resolved via
  approximate IP geolocation (`ip-api.com`, no API key, HTTP only).
- `days` — forecast length for `forecast`, 1..16, default 7.
- `months` — seasonal forecast length for `seasonal`, 1..7, default 1.
- `start_date`, `end_date` — `YYYY-MM-DD`, required for `historical`.

## Sections

- `current` — temperature, relative humidity, near-term precipitation
  probability, a short weather description, plus a brief air-quality
  summary (`european_aqi` + category). Default section.
- `forecast` — per-day min/max temperature, precipitation probability,
  weather description, for `days` days ahead. Explicit request only
  ("tomorrow", "next week", a specific date range).
- `historical` — per-day min/max temperature and precipitation for a
  past date range (`start_date`..`end_date`). Explicit only.
- `seasonal` — per-day min/max temperature and precipitation up to
  `months` months ahead (seasonal/ensemble model, lower confidence than
  `forecast`). Explicit only.
- `flood` — per-day river discharge (m³/s) for the next 7 days. Explicit
  only.
- `air_quality` — detailed pollutant breakdown (`european_aqi`,
  `us_aqi`, `pm10`, `pm2_5`, `carbon_monoxide`, `nitrogen_dioxide`,
  `sulphur_dioxide`, `ozone`) plus category. Explicit only — `current`
  already includes a one-line summary.

Every section's `location` field reports the resolved place (`name`,
`country`, `admin1`, coordinates, and `source`: `geocoding`, `ip` or
`coordinates`) so a wrong city match is visible instead of silent.

## Output and error format

- One requested section — its result prints unwrapped; several — an
  object keyed by section name.
- Invalid arguments (bad JSON, unknown section, conflicting
  `city`/`lat`/`lon`, out-of-range `days`/`months`, missing
  `start_date`/`end_date` for `historical`) — this is caught before any
  network call: `{"error": "invalid arguments: ..."}`, exit 1.
- A failed collector (city not found, network/sandbox blocks the
  request, upstream API error) — `"error"` inside that section's
  result, exit 0. Inside `current`, a failed air-quality lookup only
  affects the nested `air_quality` field; the rest of the weather data
  still comes back, since location and weather are required but AQI is
  a best-effort addition.
- If the execution sandbox blocks outbound network access, request
  permission through the environment's approval mechanism and rerun
  this same tool outside the sandbox. Never bypass a denied approval or
  fetch weather data with alternative commands (`curl`, `requests`,
  manual HTTP calls). If the approved run still fails, report the
  error; do not claim successful diagnostics.

## Interpretation

- Air quality: use the official EAQI scale for `european_aqi` — 0–20
  good, 20–40 fair, 40–60 moderate, 60–80 poor, 80–100 very poor, >100
  extremely poor (also returned as `category`).
- Precipitation probability above ~50% is worth flagging as "осадки
  вероятны" (umbrella-worthy).
- `location.source == "ip"` means the position is approximate
  (city/region-level, from the requester's IP), not an exact point —
  say so in the answer. `source == "geocoding"` or `"coordinates"` is
  an exact match to the requested place/point.
- `seasonal` forecasts are lower-confidence than `forecast` — frame them
  as an outlook, not a firm prediction.
