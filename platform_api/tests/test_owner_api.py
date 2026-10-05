import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pyotp
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app import main
from app.database import Base
from app.models import AdminAccount, User


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = test_sessions()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(main.settings, "session_secret", "t" * 48)
    monkeypatch.setattr(main.settings, "totp_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(main.settings, "bootstrap_token", "b" * 48)
    monkeypatch.setattr(main.settings, "session_cookie_secure", False)
    main.app.dependency_overrides[main.get_db] = override_db
    with TestClient(main.app) as test_client:
        test_client.app.state.test_sessions = test_sessions
        yield test_client
    main.app.dependency_overrides.clear()
    engine.dispose()


def bootstrap_owner(client):
    response = client.post("/api/v1/auth/bootstrap", json={
        "bootstrap_token": "b" * 48,
        "email": "owner@example.com",
        "display_name": "Platform Owner",
        "password": "StrongOwner#Password2026",
    })
    assert response.status_code == 201
    return response


def test_owner_bootstrap_is_one_time_and_uses_secure_session_cookie(client):
    response = bootstrap_owner(client)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=strict" in response.headers["set-cookie"].lower()
    assert response.json()["account_type"] == "owner"
    assert client.get("/api/v1/auth/me").json()["totp_enabled"] is False
    assert client.post("/api/v1/auth/bootstrap", json={
        "bootstrap_token": "b" * 48,
        "email": "second@example.com", "display_name": "Other", "password": "StrongOwner#Password2026",
    }).status_code == 409


def test_owner_bootstrap_rejects_incorrect_operator_token(client):
    response = client.post("/api/v1/auth/bootstrap", json={
        "bootstrap_token": "x" * 48, "email": "attacker@example.com", "display_name": "Attacker",
        "password": "StrongOwner#Password2026",
    })
    assert response.status_code == 403
    assert client.get("/api/v1/status").json()["owner_registered"] is False


def test_owner_setup_values_persist_and_registration_stays_closed(client):
    bootstrap_owner(client)
    response = client.put("/api/v1/owner/setup", headers={"X-Reauth-Password": "StrongOwner#Password2026"}, json={
        "section": "platform", "value": {"name": "DragonForge", "description": "Market decision support."},
    })
    assert response.status_code == 200
    setup = client.get("/api/v1/owner/setup").json()
    assert setup["values"]["platform"]["name"] == "DragonForge"
    assert setup["sections"]["platform"]["complete"] is True
    assert setup["sections"]["payments"]["complete"] is False
    assert setup["registration_enabled"] is False
    status = client.get("/api/v1/status").json()
    assert status["registration_enabled"] is False
    assert status["market_data"] == "ECB PUBLIC REFERENCE RATES (ON DEMAND)"


def test_totp_enrollment_and_recovery_codes_are_one_use(client):
    bootstrap_owner(client)
    setup = client.post("/api/v1/auth/2fa/setup", headers={"X-Reauth-Password": "StrongOwner#Password2026"})
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    enabled = client.post("/api/v1/auth/2fa/enable", json={
        "code": pyotp.TOTP(secret).now(), "password": "StrongOwner#Password2026",
    })
    assert enabled.status_code == 200
    recovery_code = enabled.json()["recovery_codes"][0]
    client.post("/api/v1/auth/logout")
    login = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "StrongOwner#Password2026", "totp_code": recovery_code,
    })
    assert login.status_code == 200
    client.post("/api/v1/auth/logout")
    reused = client.post("/api/v1/auth/login", json={
        "email": "owner@example.com", "password": "StrongOwner#Password2026", "totp_code": recovery_code,
    })
    assert reused.status_code == 401


def test_owner_can_create_only_five_individual_admins_with_scoped_permissions(client):
    bootstrap_owner(client)
    for number in range(1, 6):
        response = client.post("/api/v1/owner/admins", headers={"X-Reauth-Password": "StrongOwner#Password2026"}, json={
            "email": f"admin{number}@example.com",
            "display_name": f"Support {number}",
            "password": f"StrongAdmin#{number}Pass2026",
            "permissions": ["users:support"],
        })
        assert response.status_code == 201
        assert response.json()["slot"] == number
    assert client.post("/api/v1/owner/admins", headers={"X-Reauth-Password": "StrongOwner#Password2026"}, json={
        "email": "admin6@example.com", "display_name": "Sixth", "password": "StrongAdmin#6Pass2026",
        "permissions": ["users:support"],
    }).status_code == 409
    listing = client.get("/api/v1/owner/admins").json()
    assert listing["limit"] == 5
    assert len(listing["admins"]) == 5
    assert listing["admins"][0]["permissions"] == ["users:support"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={
        "email": "admin1@example.com", "password": "StrongAdmin#1Pass2026",
    })
    assert client.get("/api/v1/owner/admins").status_code == 403


def test_admin_passwords_are_stored_only_as_hashes(client):
    bootstrap_owner(client)
    response = client.post("/api/v1/owner/admins", headers={"X-Reauth-Password": "StrongOwner#Password2026"}, json={
        "email": "admin@example.com", "display_name": "Admin", "password": "StrongAdmin#Password2026",
        "permissions": ["security:alerts"],
    })
    assert response.status_code == 201
    db = client.app.state.test_sessions()
    try:
        admin = db.scalar(select(User).where(User.account_type == "admin"))
        assert admin.password_hash != "StrongAdmin#Password2026"
        assert db.scalar(select(AdminAccount).where(AdminAccount.user_id == admin.id)).slot == 1
    finally:
        db.close()


def test_fx_reference_rates_require_authentication(client):
    response = client.get("/api/v1/markets/fx")

    assert response.status_code == 401


def test_authenticated_fx_endpoint_returns_source_and_reference_data(client, monkeypatch):
    from app import main

    payload = {
        "source": "European Central Bank (ECB)",
        "source_url": "https://data.ecb.europa.eu/data/datasets/EXR",
        "series": "ECB daily reference exchange rates, currencies per EUR",
        "frequency": "Daily business-day observations",
        "fetched_at": "2026-10-05T12:00:00+00:00",
        "cache_seconds": 900,
        "rates": [{"currency": "USD", "units_per_eur": 1.17}],
        "disclaimer": "Reference rates, not executable prices.",
    }
    monkeypatch.setattr(main, "fetch_ecb_reference_rates", lambda: payload)
    bootstrap_owner(client)

    response = client.get("/api/v1/markets/fx")

    assert response.status_code == 200
    assert response.json() == payload


def test_fx_endpoint_reports_upstream_failure_without_fabricating_data(client, monkeypatch):
    from app import main
    from app.market_data import MarketDataUnavailable

    def unavailable():
        raise MarketDataUnavailable("upstream unavailable")

    monkeypatch.setattr(main, "fetch_ecb_reference_rates", unavailable)
    bootstrap_owner(client)

    response = client.get("/api/v1/markets/fx")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Public ECB reference-rate data is temporarily unavailable"
    }


def test_macro_indicators_require_authentication(client):
    assert client.get("/api/v1/markets/macro").status_code == 401


def test_authenticated_macro_endpoint_returns_public_data(client, monkeypatch):
    from app import main

    payload = {
        "source": "World Bank Open Data",
        "source_url": "https://data.worldbank.org/",
        "api_url": "https://api.worldbank.org/v2/country/all/indicator",
        "frequency": "Annual observations",
        "fetched_at": "2026-10-05T12:00:00+00:00",
        "cache_seconds": 21600,
        "indicators": [["FP.CPI.TOTL.ZG", "Inflation"]],
        "countries": [{"country_code": "US", "country": "United States", "indicators": []}],
        "disclaimer": "Annual historical statistics.",
    }
    monkeypatch.setattr(main, "fetch_macro_indicators", lambda: payload)
    bootstrap_owner(client)

    response = client.get("/api/v1/markets/macro")

    assert response.status_code == 200
    assert response.json() == payload