from datetime import UTC, datetime, timedelta

import jwt
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_different_value() -> None:
    password = "StrongPassword123!"

    hashed_password = hash_password(password)

    assert hashed_password != password


def test_hash_password_generates_unique_hashes() -> None:
    password = "StrongPassword123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash


def test_verify_password_with_correct_password() -> None:
    password = "StrongPassword123!"
    hashed_password = hash_password(password)

    assert verify_password(password, hashed_password) is True


def test_verify_password_with_incorrect_password() -> None:
    hashed_password = hash_password("StrongPassword123!")

    assert verify_password("WrongPassword123!", hashed_password) is False


def test_create_access_token_returns_valid_token() -> None:
    token = create_access_token("1")

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == "1"
    assert "iat" in payload
    assert "exp" in payload


def test_create_access_token_has_configured_expiration() -> None:
    token = create_access_token("1")

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)

    expected_duration = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    assert expires_at - issued_at == expected_duration


def test_decode_access_token_returns_payload() -> None:
    token = create_access_token("123")

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "123"


def test_decode_access_token_rejects_expired_token() -> None:
    now = datetime.now(UTC)

    token = jwt.encode(
        {
            "sub": "123",
            "iat": now - timedelta(minutes=30),
            "exp": now - timedelta(minutes=15),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert decode_access_token(token) is None


def test_decode_access_token_rejects_manipulated_token() -> None:
    token = create_access_token("123")
    manipulated_token = f"{token[:-1]}{'a' if token[-1] != 'a' else 'b'}"

    assert decode_access_token(manipulated_token) is None


def test_decode_access_token_rejects_different_secret() -> None:
    token = jwt.encode(
        {"sub": "123"},
        "a-different-secret-key",
        algorithm=settings.jwt_algorithm,
    )

    assert decode_access_token(token) is None


def test_decode_access_token_rejects_missing_subject() -> None:
    token = jwt.encode(
        {"iat": datetime.now(UTC)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    assert decode_access_token(token) is None
