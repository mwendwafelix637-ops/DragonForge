from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


WORLD_BANK_SOURCE = "World Bank Open Data"
WORLD_BANK_SOURCE_URL = "https://data.worldbank.org/"
WORLD_BANK_API_URL = "https://api.worldbank.org/v2/country/all/indicator"
COUNTRIES = {
    "AU": "Australia",
    "BR": "Brazil",
    "CA": "Canada",
    "CN": "China",
    "DE": "Germany",
    "FR": "France",
    "GB": "United Kingdom",
    "IN": "India",
    "JP": "Japan",
    "KR": "South Korea",
    "SG": "Singapore",
    "US": "United States",
}
INDICATORS = {
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
    "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
}
CACHE_SECONDS = 6 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 2_000_000

_cache_lock = Lock()
_cached_at = 0.0
_cached_data: dict | None = None


class MacroDataUnavailable(Exception):
    pass


def _fetch_indicator(indicator_id: str) -> list[dict]:
    query = urlencode({"format": "json", "mrv": "1", "per_page": "1000"})
    request = Request(
        f"{WORLD_BANK_API_URL}/{indicator_id}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "DragonForge/0.1 public-reference-data",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise MacroDataUnavailable("World Bank Open Data service could not be reached") from exc

    if len(content) > MAX_RESPONSE_BYTES:
        raise MacroDataUnavailable("World Bank response exceeded the maximum accepted size")
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MacroDataUnavailable("World Bank response was not valid JSON") from exc

    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or not isinstance(payload[0], dict)
        or not isinstance(payload[1], list)
    ):
        raise MacroDataUnavailable("World Bank response did not match the expected API format")

    rows = []
    for row in payload[1]:
        if not isinstance(row, dict):
            continue
        country = row.get("country") or {}
        country_code = country.get("id")
        year = row.get("date")
        value = row.get("value")
        try:
            numeric_value = float(value)
            numeric_year = int(year)
        except (TypeError, ValueError):
            continue
        if country_code in COUNTRIES and math.isfinite(numeric_value):
            rows.append({
                "country_code": country_code,
                "country": COUNTRIES[country_code],
                "year": numeric_year,
                "value": numeric_value,
            })
    return rows


def fetch_macro_indicators() -> dict:
    global _cached_at, _cached_data

    with _cache_lock:
        now = monotonic()
        if _cached_data is not None and now - _cached_at < CACHE_SECONDS:
            return _cached_data

        try:
            with ThreadPoolExecutor(max_workers=len(INDICATORS)) as executor:
                futures = {
                    indicator_id: executor.submit(_fetch_indicator, indicator_id)
                    for indicator_id in INDICATORS
                }
                results = {
                    indicator_id: futures[indicator_id].result()
                    for indicator_id in INDICATORS
                }
        except MacroDataUnavailable:
            raise
        except Exception as exc:
            raise MacroDataUnavailable("World Bank indicators could not be retrieved") from exc

        grouped = {code: {"country_code": code, "country": name, "indicators": []}
                   for code, name in COUNTRIES.items()}
        for indicator_id, indicator_name in INDICATORS.items():
            for row in results[indicator_id]:
                grouped[row["country_code"]]["indicators"].append({
                    "id": indicator_id,
                    "name": indicator_name,
                    "year": row["year"],
                    "value": row["value"],
                })

        observations = [
            country for country in grouped.values()
            if country["indicators"]
        ]
        if not observations:
            raise MacroDataUnavailable("World Bank returned no supported country observations")

        result = {
            "source": WORLD_BANK_SOURCE,
            "source_url": WORLD_BANK_SOURCE_URL,
            "api_url": WORLD_BANK_API_URL,
            "frequency": "Annual observations; latest available year can vary by country and indicator",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_seconds": CACHE_SECONDS,
            "indicators": list(INDICATORS.items()),
            "countries": observations,
            "disclaimer": (
                "These are annual historical macroeconomic statistics, not current market prices "
                "or forecasts. Reporting years and publication dates vary by country and series."
            ),
        }
        _cached_data = result
        _cached_at = monotonic()
        return result
