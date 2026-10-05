import json
from io import BytesIO

import pytest

from app import macro_data
from app.macro_data import MacroDataUnavailable


def test_world_bank_indicator_parser_selects_supported_countries(monkeypatch):
    payload = [
        {"page": 1, "pages": 1, "total": 3},
        [
            {"country": {"id": "US"}, "date": "2025", "value": 2.5},
            {"country": {"id": "GB"}, "date": "2024", "value": 1.2},
            {"country": {"id": "ZZ"}, "date": "2025", "value": 9.9},
            {"country": {"id": "JP"}, "date": "2025", "value": None},
        ],
    ]

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        macro_data,
        "urlopen",
        lambda request, timeout: FakeResponse(json.dumps(payload).encode()),
    )
    rows = macro_data._fetch_indicator("FP.CPI.TOTL.ZG")

    assert rows == [
        {"country_code": "US", "country": "United States", "year": 2025, "value": 2.5},
        {"country_code": "GB", "country": "United Kingdom", "year": 2024, "value": 1.2},
    ]


def test_world_bank_parser_rejects_invalid_response_shape(monkeypatch):
    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        macro_data, "urlopen", lambda request, timeout: FakeResponse(b'{"unexpected": true}')
    )

    with pytest.raises(MacroDataUnavailable, match="expected API format"):
        macro_data._fetch_indicator("FP.CPI.TOTL.ZG")


def test_macro_fetch_groups_indicator_observations_and_caches(monkeypatch):
    calls = []

    def fake_fetch(indicator_id):
        calls.append(indicator_id)
        return [{
            "country_code": "US",
            "country": "United States",
            "year": 2025,
            "value": 2.5 if indicator_id == "FP.CPI.TOTL.ZG" else 2.1,
        }]

    monkeypatch.setattr(macro_data, "_fetch_indicator", fake_fetch)
    monkeypatch.setattr(macro_data, "_cached_data", None)
    monkeypatch.setattr(macro_data, "_cached_at", 0)

    first = macro_data.fetch_macro_indicators()
    second = macro_data.fetch_macro_indicators()

    assert first is second
    assert len(calls) == 2
    assert first["source"] == "World Bank Open Data"
    assert first["countries"][0]["country_code"] == "US"
    assert {item["id"] for item in first["countries"][0]["indicators"]} == set(macro_data.INDICATORS)
