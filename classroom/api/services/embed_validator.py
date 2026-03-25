"""Embed URL whitelist validator to prevent SSRF and malicious iframe injection."""
from urllib.parse import urlparse
from typing import Optional

ALLOWED_EMBED_DOMAINS: set[str] = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "drive.google.com",
    "docs.google.com",
    "loom.com",
    "www.loom.com",
    "onedrive.live.com",
    "1drv.ms",
    "vimeo.com",
    "www.vimeo.com",
    "player.vimeo.com",
}


def is_allowed_embed_url(url: str) -> bool:
    """Return True if the URL's domain is in the embed whitelist."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().lstrip("www.")
        # Check exact domain or subdomain
        return any(
            host == domain or host.endswith("." + domain)
            for domain in ALLOWED_EMBED_DOMAINS
        )
    except Exception:
        return False


def transform_to_embed_url(url: str, resource_type: str) -> Optional[str]:
    """Convert share-URL to embeddable URL for supported services."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtube.com" in host or "youtu.be" in host:
        video_id = _youtube_id(url)
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

    if "drive.google.com" in host:
        # https://drive.google.com/file/d/{id}/view -> preview
        parts = parsed.path.split("/")
        if "d" in parts:
            idx = parts.index("d")
            if idx + 1 < len(parts):
                fid = parts[idx + 1]
                return f"https://drive.google.com/file/d/{fid}/preview"

    if "loom.com" in host:
        # https://www.loom.com/share/{id} -> embed
        share_id = parsed.path.rstrip("/").split("/")[-1]
        return f"https://www.loom.com/embed/{share_id}"

    if "vimeo.com" in host:
        video_id = parsed.path.strip("/").split("/")[0]
        return f"https://player.vimeo.com/video/{video_id}"

    # Default: return as-is for links opened in new tab
    return url


def _youtube_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/")
    query = dict(q.split("=", 1) for q in parsed.query.split("&") if "=" in q)
    return query.get("v")
