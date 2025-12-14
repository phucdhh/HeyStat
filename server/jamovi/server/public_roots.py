from urllib.parse import urlparse


def build_public_roots(roots, headers):
    """Given configured internal `roots` and incoming request `headers`,
    build public-facing roots honoring standard reverse-proxy headers.

    - X-Forwarded-Host overrides Host
    - X-Forwarded-Proto sets the scheme (http/https)
    - X-Forwarded-Prefix is prepended to the path to support subpath mounts
    """
    forwarded = headers.get('X-Forwarded-Host') or headers.get('Host')
    proto = headers.get('X-Forwarded-Proto', None)
    prefix = headers.get('X-Forwarded-Prefix', '')

    if not forwarded:
        return list(roots)

    new_roots = []
    for r in roots:
        parsed = urlparse('//' + r)
        orig_path = parsed.path or ''
        if prefix:
            p = prefix.rstrip('/')
            if not p.startswith('/'):
                p = '/' + p
            path = p + orig_path
        else:
            path = orig_path
        # sanitize forwarded host: strip any scheme or path if present
        fwd = forwarded
        try:
            if '://' in fwd:
                p = urlparse(fwd)
                fwd_host = p.netloc
            else:
                # urlparse requires // to parse netloc, so add it
                f = urlparse('//' + fwd)
                fwd_host = f.netloc or fwd.split('/')[0]
        except Exception:
            fwd_host = fwd.split('/')[0]

        if proto:
            url = f'{ proto }://{ fwd_host }{ path }'
        else:
            url = f'{ fwd_host }{ path }'
        
        # Ensure trailing slash for consistency with browser expectations
        if not url.endswith('/'):
            url += '/'
        
        new_roots.append(url)

    return new_roots
