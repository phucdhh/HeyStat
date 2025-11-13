import pytest
from jamovi.server.server import build_public_roots


def test_no_forwarded_headers_returns_original_roots():
    roots = ['localhost:41337', 'localhost:41338', 'localhost:41339']
    headers = {}
    new = build_public_roots(roots, headers)
    assert new == roots


def test_forwarded_host_proto_and_prefix_applied():
    roots = ['internal:41337', 'internal:41338', 'internal:41339']
    headers = {
        'X-Forwarded-Host': 'public.example.com:6789',
        'X-Forwarded-Proto': 'https',
        'X-Forwarded-Prefix': '/jamovi'
    }
    new = build_public_roots(roots, headers)
    # Expect each root to start with https://public.example.com:6789/jamovi
    for r in new:
        assert r.startswith('https://public.example.com:6789/jamovi')
