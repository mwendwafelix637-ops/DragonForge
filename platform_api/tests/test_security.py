import pytest

from app.security import hash_password, verify_password, create_totp_secret, verify_totp


def test_password_hash_is_not_reversible_and_verifies():
    password = "ResearchOnly#2026Secure"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


@pytest.mark.parametrize("password", ["short", "alllowercase123!", "NOLOWERCASE123!"])
def test_weak_passwords_are_rejected(password):
    with pytest.raises(ValueError):
        hash_password(password)


def test_totp_code_verifies():
    import pyotp

    secret = create_totp_secret()
    assert verify_totp(secret, pyotp.TOTP(secret).now())
    assert not verify_totp(secret, "000000")