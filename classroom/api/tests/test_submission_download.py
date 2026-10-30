"""The teacher's «Tải về» link in the submissions table points here."""
from routers.submissions import router


def test_download_route_is_registered():
    paths = [r.path for r in router.routes if "GET" in getattr(r, "methods", set())]
    assert "/submissions/{submission_id}/download" in paths
