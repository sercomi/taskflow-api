from app.core.security import hash_password, verify_password


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
