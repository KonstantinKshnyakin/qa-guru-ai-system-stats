#!/usr/bin/env python3
"""weather tool: open-meteo diagnostics as a JSON report.

Arguments arrive as JSON in TOOL_ARGS, stdout is
the tool result. Read-only, stdlib only. One requested section prints its
result unwrapped; several print an object keyed by section name. Invalid
arguments print {"error": ...} and exit 1; a failed collector puts "error"
inside its section while the tool still exits 0.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HTTP_TIMEOUT = 10
DEFAULT_LANGUAGE = "ru"
DEFAULT_FORECAST_DAYS = 7
MAX_FORECAST_DAYS = 16
DEFAULT_SEASONAL_MONTHS = 1
MAX_SEASONAL_MONTHS = 7
FLOOD_FORECAST_DAYS = 7

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
IP_GEO_URL = "http://ip-api.com/json/"

WMO_WEATHER_TEXT = {
    0: "ясно",
    1: "в основном ясно",
    2: "переменная облачность",
    3: "облачно",
    45: "туман",
    48: "туман с инееем",
    51: "лёгкая морось",
    53: "умеренная морось",
    55: "сильная морось",
    56: "лёгкая ледяная морось",
    57: "сильная ледяная морось",
    61: "небольшой дождь",
    63: "умеренный дождь",
    65: "сильный дождь",
    66: "лёгкий ледяной дождь",
    67: "сильный ледяной дождь",
    71: "небольшой снег",
    73: "умеренный снег",
    75: "сильный снег",
    77: "снежные зёрна",
    80: "небольшие ливни",
    81: "умеренные ливни",
    82: "сильные ливни",
    85: "небольшой снегопад ливнями",
    86: "сильный снегопад ливнями",
    95: "гроза",
    96: "гроза с небольшим градом",
    99: "гроза с сильным градом",
}


def _get_json(url, params):
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(
        f"{url}?{query}", headers={"User-Agent": "weather-skill-tool/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ValueError(f"HTTP {e.code} from {url}: {body[:200]}") from e
    except urllib.error.URLError as e:
        raise ValueError(f"network error contacting {url}: {e.reason}") from e


def _section(fn):
    """Run a collector; on failure report the error inside the section."""
    try:
        return fn()
    except Exception as e:
        return {"error": str(e)}


def _nth(values, i):
    return values[i] if values and i < len(values) else None


def _pick_hourly(hourly, field, reference_time=None):
    times = hourly.get("time") or []
    values = hourly.get(field) or []
    if not times or not values:
        return None
    if reference_time:
        ref_hour = reference_time[:13]
        for t, v in zip(times, values):
            if t[:13] >= ref_hour:
                return v
    return values[0]


def _weather_code_text(code):
    if code is None:
        return None
    return WMO_WEATHER_TEXT.get(int(code), f"код {code}")


def _eaqi_category(value):
    if value is None:
        return None
    if value <= 20:
        return "good"
    if value <= 40:
        return "fair"
    if value <= 60:
        return "moderate"
    if value <= 80:
        return "poor"
    if value <= 100:
        return "very poor"
    return "extremely poor"


def geocode(city, language=DEFAULT_LANGUAGE):
    data = _get_json(GEOCODING_URL, {"name": city, "count": 1, "language": language})
    results = data.get("results") or []
    if not results:
        raise ValueError(f"city not found: {city!r}")
    r = results[0]
    return {
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "name": r.get("name", city),
        "country": r.get("country", ""),
        "admin1": r.get("admin1", ""),
        "elevation": r.get("elevation"),
        "source": "geocoding",
    }


def ip_geolocate():
    data = _get_json(IP_GEO_URL, {"fields": "status,message,lat,lon,city,country"})
    if data.get("status") != "success":
        raise ValueError(f"ip geolocation failed: {data.get('message', 'unknown error')}")
    return {
        "latitude": data["lat"],
        "longitude": data["lon"],
        "name": data.get("city", ""),
        "country": data.get("country", ""),
        "admin1": "",
        "elevation": None,
        "source": "ip",
    }


def resolve_location(loc_spec):
    city = loc_spec.get("city")
    lat = loc_spec.get("lat")
    lon = loc_spec.get("lon")
    if city:
        return geocode(city)
    if lat is not None and lon is not None:
        return {
            "latitude": lat,
            "longitude": lon,
            "name": "",
            "country": "",
            "admin1": "",
            "elevation": None,
            "source": "coordinates",
        }
    return ip_geolocate()


def _location_summary(loc):
    return {
        "name": loc["name"],
        "country": loc["country"],
        "admin1": loc["admin1"],
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "source": loc["source"],
    }


def _fetch_brief_aqi(loc):
    data = _get_json(
        AIR_QUALITY_URL,
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "hourly": "european_aqi",
            "forecast_days": 1,
            "timezone": "auto",
        },
    )
    value = _pick_hourly(data.get("hourly", {}), "european_aqi")
    return {"european_aqi": value, "category": _eaqi_category(value)}


def collect_current(loc_spec):
    loc = resolve_location(loc_spec)
    weather = _get_json(
        FORECAST_URL,
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
            "hourly": "precipitation_probability",
            "forecast_days": 1,
            "timezone": "auto",
            "elevation": loc.get("elevation"),
        },
    )
    current = weather.get("current", {})
    precip_probability = _pick_hourly(
        weather.get("hourly", {}), "precipitation_probability", current.get("time")
    )
    return {
        "location": _location_summary(loc),
        "temperature_c": current.get("temperature_2m"),
        "relative_humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_probability_pct": precip_probability,
        "weather_code": current.get("weather_code"),
        "weather_text": _weather_code_text(current.get("weather_code")),
        "air_quality": _section(lambda: _fetch_brief_aqi(loc)),
    }


def collect_forecast(loc_spec, days):
    loc = resolve_location(loc_spec)
    data = _get_json(
        FORECAST_URL,
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "forecast_days": days,
            "timezone": "auto",
            "elevation": loc.get("elevation"),
        },
    )
    daily = data.get("daily", {})
    days_out = []
    for i, date in enumerate(daily.get("time", [])):
        code = _nth(daily.get("weather_code"), i)
        days_out.append(
            {
                "date": date,
                "temp_min_c": _nth(daily.get("temperature_2m_min"), i),
                "temp_max_c": _nth(daily.get("temperature_2m_max"), i),
                "precipitation_probability_pct": _nth(
                    daily.get("precipitation_probability_max"), i
                ),
                "weather_code": code,
                "weather_text": _weather_code_text(code),
            }
        )
    return {"location": _location_summary(loc), "days": days_out}


def collect_historical(loc_spec, start_date, end_date):
    loc = resolve_location(loc_spec)
    data = _get_json(
        HISTORICAL_URL,
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        },
    )
    daily = data.get("daily", {})
    days_out = [
        {
            "date": date,
            "temp_min_c": _nth(daily.get("temperature_2m_min"), i),
            "temp_max_c": _nth(daily.get("temperature_2m_max"), i),
            "precipitation_mm": _nth(daily.get("precipitation_sum"), i),
        }
        for i, date in enumerate(daily.get("time", []))
    ]
    return {"location": _location_summary(loc), "days": days_out}


def collect_seasonal(loc_spec, months):
    loc = resolve_location(loc_spec)
    data = _get_json(
        SEASONAL_URL,
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": min(months * 30, 210),
            "timezone": "auto",
        },
    )
    daily = data.get("daily", {})
    days_out = [
        {
            "date": date,
            "temp_min_c": _nth(daily.get("temperature_2m_min"), i),
            "temp_max_c": _nth(daily.get("temperature_2m_max"), i),
            "precipitation_mm": _nth(daily.get("precipitation_sum"), i),
        }
        for i, date in enumerate(daily.get("time", []))
    ]
    return {"location": _location_summary(loc), "days": days_out}


def collect_flood(loc_spec):
    loc = resolve_location(loc_spec)
    data = _get_json(
        FLOOD_URL,
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "daily": "river_discharge",
            "forecast_days": FLOOD_FORECAST_DAYS,
            "timezone": "auto",
        },
    )
    daily = data.get("daily", {})
    days_out = [
        {"date": date, "river_discharge_m3s": _nth(daily.get("river_discharge"), i)}
        for i, date in enumerate(daily.get("time", []))
    ]
    return {"location": _location_summary(loc), "days": days_out}


def collect_air_quality(loc_spec):
    loc = resolve_location(loc_spec)
    fields = [
        "european_aqi",
        "us_aqi",
        "pm10",
        "pm2_5",
        "carbon_monoxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
    ]
    data = _get_json(
        AIR_QUALITY_URL,
        {
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "hourly": ",".join(fields),
            "forecast_days": 1,
            "timezone": "auto",
        },
    )
    hourly = data.get("hourly", {})
    values = {field: _pick_hourly(hourly, field) for field in fields}
    return {
        "location": _location_summary(loc),
        **values,
        "category": _eaqi_category(values.get("european_aqi")),
    }


SECTIONS = {
    "current": collect_current,
    "forecast": collect_forecast,
    "historical": collect_historical,
    "seasonal": collect_seasonal,
    "flood": collect_flood,
    "air_quality": collect_air_quality,
}


def _int_arg(args, name, default, lo, hi):
    v = args.get(name, default)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{name} must be an integer, got {v!r}")
    if not lo <= v <= hi:
        raise ValueError(f"{name} must be {lo}..{hi}, got {v}")
    return v


def _date_arg(args, name, required):
    v = args.get(name)
    if v is None:
        if required:
            raise ValueError(f"{name} is required for section 'historical'")
        return None
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError(f"{name} must be a date string YYYY-MM-DD, got {v!r}")
    return v


def _location_args(args):
    city = args.get("city")
    lat = args.get("lat")
    lon = args.get("lon")

    if city is not None:
        if not isinstance(city, str) or not city.strip():
            raise ValueError(f"city must be a non-empty string, got {city!r}")

    has_city = bool(city)
    has_lat, has_lon = lat is not None, lon is not None

    if has_city and (has_lat or has_lon):
        raise ValueError("provide either 'city' or 'lat'/'lon', not both")
    if has_lat != has_lon:
        raise ValueError("'lat' and 'lon' must be provided together")

    if has_lat:
        if (
            isinstance(lat, bool)
            or isinstance(lon, bool)
            or not isinstance(lat, (int, float))
            or not isinstance(lon, (int, float))
        ):
            raise ValueError(f"lat/lon must be numbers, got lat={lat!r} lon={lon!r}")
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValueError(f"lat/lon out of range: lat={lat!r} lon={lon!r}")

    return {
        "city": city if has_city else None,
        "lat": float(lat) if has_lat else None,
        "lon": float(lon) if has_lon else None,
    }


def main() -> int:
    try:
        args = json.loads(os.environ.get("TOOL_ARGS", "{}"))
        if not isinstance(args, dict):
            raise ValueError("TOOL_ARGS must be a JSON object")
        section = args.get("section", "current")
        if not isinstance(section, str):
            raise ValueError(f"section must be a string, got {section!r}")
        names = list(dict.fromkeys(s.strip() for s in section.split(",") if s.strip()))
        if not names:
            raise ValueError("section must not be empty")
        bad = sorted(set(names) - set(SECTIONS))
        if bad:
            raise ValueError(
                f"unknown section(s): {', '.join(bad)} (valid: {', '.join(SECTIONS)})"
            )

        loc_spec = _location_args(args)
        days = _int_arg(args, "days", DEFAULT_FORECAST_DAYS, 1, MAX_FORECAST_DAYS)
        months = _int_arg(args, "months", DEFAULT_SEASONAL_MONTHS, 1, MAX_SEASONAL_MONTHS)
        start_date = _date_arg(args, "start_date", required="historical" in names)
        end_date = _date_arg(args, "end_date", required="historical" in names)
    except (ValueError, TypeError) as e:
        print(json.dumps({"error": f"invalid arguments: {e}"}))
        return 1

    report = {}
    for name in names:
        fn = SECTIONS[name]
        if name == "forecast":
            report[name] = _section(lambda: fn(loc_spec, days))
        elif name == "historical":
            report[name] = _section(lambda: fn(loc_spec, start_date, end_date))
        elif name == "seasonal":
            report[name] = _section(lambda: fn(loc_spec, months))
        else:
            report[name] = _section(lambda: fn(loc_spec))

    print(json.dumps(report if len(report) > 1 else report[names[0]], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
