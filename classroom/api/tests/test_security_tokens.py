from jose import JWTError

from auth.security import create_access_token, create_refresh_token, decode_access_token


def test_access_token_roundtrip_contains_required_fields() -> None:
    token = create_access_token("00000000-0000-0000-0000-000000000001", ["user", "teacher"])
    payload = decode_access_token(token)

    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert payload["type"] == "access"
    assert set(payload["roles"]) == {"user", "teacher"}
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload


def test_decode_rejects_wrong_token_type() -> None:
    # Refresh tokens are opaque random hex strings, not JWT access tokens.
    refresh_token = create_refresh_token("00000000-0000-0000-0000-000000000001")

    try:
        decode_access_token(refresh_token)
        assert False, "Expected JWTError for non-JWT token"
    except JWTError:
        assert True


def test_refresh_token_format_is_hex_64_chars() -> None:
    token = create_refresh_token("00000000-0000-0000-0000-000000000001")

    assert len(token) == 64
    int(token, 16)
