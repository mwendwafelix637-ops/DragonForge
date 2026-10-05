from io import BytesIO

import pytest

from app import market_data
from app.market_data import MarketDataUnavailable


def test_parse_ecb_csv_uses_two_observations_and_computes_daily_change():
    rates = market_data._parse_ecb_csv(
        "CURRENCY,TIME_PERIOD,OBS_VALUE\n"
        "USD,2026-10-02,1.17\n"
        "USD,2026-10-05,1.20\n"
        "GBP,2026-10-05,0.86\n"
        "XXX,2026-10-05,99\n"
        "JPY,2026-10-05,.. \n"
    )

    rates_by_currency = {rate["currency"]: rate for rate in rates}
    assert set(rates_by_currency) == {"USD", "GBP"}
    assert rates_by_currency["USD"]["units_per_eur"] == 1.2
    assert rates_by_currency["USD"]["previous_observation_date"] == "2026-10-02"
    assert rates_by_currency["USD"]["change_pct"] == pytest.approx((1.2 / 1.17 - 1) * 100)
    assert rates_by_currency["GBP"]["change_pct"] is None


def test_parse_ecb_csv_rejects_unexpected_schema():
    with pytest.raises(MarketDataUnavailable, match="expected CSV fields"):
        market_data._parse_ecb_csv("currency,value\nUSD,1.2\n")


def test_parse_ecb_csv_fails_when_no_supported_observations_exist():
    with pytest.raises(MarketDataUnavailable, match="no supported currency"):
        market_data._parse_ecb_csv("CURRENCY,TIME_PERIOD,OBS_VALUE\nXXX,2026-10-05,1.2\n")


def test_ecb_fetch_is_cached_and_requests_bounded_observations(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return BytesIO(
            b"CURRENCY,TIME_PERIOD,OBS_VALUE\n"
            b"USD,2026-10-02,1.17\nUSD,2026-10-05,1.20\n"
        )

    monkeypatch.setattr(market_data, "urlopen", fake_urlopen)
    monkeypatch.setattr(market_data, "_cached_data", None)
    monkeypatch.setattr(market_data, "_cached_at", 0)

    first = market_data.fetch_ecb_reference_rates()
    second = market_data.fetch_ecb_reference_rates()

    assert first is second
    assert len(calls) == 1
    assert calls[0][1] == market_data.REQUEST_TIMEOUT_SECONDS
    assert "lastNObservations=2" in calls[0][0].full_url
    assert first["source"] == "European Central Bank (ECB)"
