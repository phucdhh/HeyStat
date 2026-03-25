from services.markdown import sanitize_md


def test_sanitize_removes_script_tags() -> None:
    raw = "<h2>OK</h2><script>alert('xss')</script>"
    sanitized = sanitize_md(raw)

    assert "<script>" not in sanitized
    assert "</script>" not in sanitized
    assert "<h2>OK</h2>" in sanitized


def test_sanitize_removes_dangerous_attributes() -> None:
    raw = '<a href="https://example.com" onclick="alert(1)">safe link</a>'
    sanitized = sanitize_md(raw)

    assert "onclick" not in sanitized
    assert 'href="https://example.com"' in sanitized


def test_sanitize_handles_none() -> None:
    assert sanitize_md(None) is None
