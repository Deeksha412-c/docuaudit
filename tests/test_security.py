import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.security import create_token, decode_token, hash_password, verify_password

SECRET = "a-secret-used-only-in-the-tests"


def test_a_password_is_hashed_and_verified():
    hashed = hash_password("correct horse battery")
    assert hashed != "correct horse battery"
    assert verify_password("correct horse battery", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_the_same_password_hashes_differently_each_time():
    assert hash_password("same password") != hash_password("same password")


def test_a_broken_hash_never_verifies():
    assert verify_password("anything", "not-a-real-hash") is False


def test_a_valid_token_returns_the_user_id():
    assert decode_token(create_token("user-1", SECRET), SECRET) == "user-1"


def test_an_expired_token_is_rejected():
    assert decode_token(create_token("user-1", SECRET, minutes=-1), SECRET) is None


def test_a_token_signed_with_another_secret_is_rejected():
    assert decode_token(create_token("user-1", "some-other-secret-value"), SECRET) is None


def test_a_tampered_token_is_rejected():
    token = create_token("user-1", SECRET)
    assert decode_token(token[:-3] + "abc", SECRET) is None
    assert decode_token("garbage", SECRET) is None
