import csv
from datetime import datetime, timezone
from io import StringIO
import math
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ECB_SOURCE = "European Central Bank (ECB)"
ECB_SOURCE_URL = "https://data.ecb.europa.eu/data/datasets/EXR"
ECB_API_URL = "https://data-api.ecb.europa.eu/service/data/EXR"
ECB_CURRENCIES = {
    "AUD": "Australian dollar",
    "CAD": "Canadian dollar",
    "CHF": "Swiss franc",
    "CNY": "Chinese yuan",
    "GBP": "Pound sterling",
    "HKD": "Hong Kong dollar",
    "INR": "Indian rupee",
    "JPY": "Japanese yen",
    "KRW": "South Korean won",
    "NZD": "New Zealand dollar",
    "SGD": "Singapore dollar",
    "USD": "US dollar",
}
CACHE_SECONDS = 15 * 60
REQUEST_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 1_000_000

_cache_lock = Lock()
_cached_at = 0.0
_cached_data: dict | None = None


class MarketDataUnavailable(Exception):
    pass


def _parse_ecb_csv(content: str) -> list[dict]:
    reader = csv.DictReader(StringIO(content))
    required = {"CURRENCY", "TIME_PERIOD", "OBS_VALUE"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise MarketDataUnavailable("ECB response did not contain the expected CSV fields")

    observations: dict[str, dict[str, float]] = {code: {} for code in ECB_CURRENCIES}
    for row in reader:
        currency = row.get("CURRENCY")
        date = row.get("TIME_PERIOD")
        raw_value = row.get("OBS_VALUE")
        if currency not in observations or not date or not raw_value:
            continue
        try:
            value = float(raw_value)
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            continue
        if math.isfinite(value) and value > 0:
            observations[currency][date] = value

    rates = []
    for currency, currency_observations in observations.items():
        recent = sorted(currency_observations.items())[-2:]
        if not recent:
            continue
        observation_date, rate = recent[-1]
        previous_date, previous_rate = recent[0] if len(recent) == 2 else (None, None)
        change_pct = ((rate / previous_rate) - 1) * 100 if previous_rate else None
        rates.append({
            "currency": currency,
            "name": ECB_CURRENCIES[currency],
            "observation_date": observation_date,
            "units_per_eur": rate,
            "previous_observation_date": previous_date,
            "previous_units_per_eur": previous_rate,
            "change_pct": change_pct,
        })

    if not rates:
        raise MarketDataUnavailable("ECB response contained no supported currency observations")
    return rates


def fetch_ecb_reference_rates() -> dict:
    global _cached_at, _cached_data

    with _cache_lock:
        now = monotonic()
        if _cached_data is not None and now - _cached_at < CACHE_SECONDS:
            return _cached_data

        series = "+".join(sorted(ECB_CURRENCIES))
        params = urlencode({"format": "csvdata", "lastNObservations": "2"})
        request = Request(
            f"{ECB_API_URL}/D.{series}.EUR.SP00.A?{params}",
            headers={
                "Accept": "text/csv",
                "User-Agent": "DragonForge/0.1 public-reference-data",
            },
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                content = response.read(MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise MarketDataUnavailable("ECB reference-rate service could not be reached") from exc

        if len(content) > MAX_RESPONSE_BYTES:
            raise MarketDataUnavailable("ECB response exceeded the maximum accepted size")
        try:
            rates = _parse_ecb_csv(content.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise MarketDataUnavailable("ECB response was not valid UTF-8 CSV") from exc

        result = {
            "source": ECB_SOURCE,
            "source_url": ECB_SOURCE_URL,
            "series": "ECB daily reference exchange rates, currencies per EUR",
            "frequency": "Daily business-day observations",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cache_seconds": CACHE_SECONDS,
            "rates": rates,
            "disclaimer": (
                "These are ECB reference rates, not intraday executable prices or investment advice. "
                "Observations are published on ECB business days and may not be current market quotes."
            ),
        }
        _cached_data = result
        _cached_at = monotonic()
        return result
