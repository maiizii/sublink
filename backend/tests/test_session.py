"""Tests for session serialization helpers."""

from backend.app.session import deserialize_session, serialize_session


def test_session_round_trip_preserves_payload() -> None:
    payload = {"user_id": 123, "username": "alice"}

    token = serialize_session(payload)

    assert deserialize_session(token) == payload


def test_tampered_session_token_is_rejected() -> None:
    token = serialize_session({"user_id": 123})

    tampered = token + "x"

    assert deserialize_session(tampered) == {}
