from datetime import datetime, timedelta

from app.models import ScanEvent, UrlMapping


# ---------------------------------------------------------------------------
# POST /api/qr/create
# ---------------------------------------------------------------------------

class TestCreate:
    def test_valid_url_returns_200(self, client):
        r = client.post("/api/qr/create", json={"url": "http://example.com"})
        assert r.status_code == 200
        body = r.json()
        assert "token" in body
        assert "/r/" in body["short_url"]
        assert body["qr_code_url"].endswith("/image")
        assert body["original_url"] == "https://example.com"

    def test_url_normalized_to_https(self, client):
        r = client.post("/api/qr/create", json={"url": "http://example.com"})
        assert r.status_code == 200
        assert r.json()["original_url"] == "https://example.com"

    def test_url_too_long_returns_422(self, client):
        long_url = "https://example.com/" + "a" * 2048
        r = client.post("/api/qr/create", json={"url": long_url})
        assert r.status_code == 422

    def test_non_http_scheme_returns_422(self, client):
        r = client.post("/api/qr/create", json={"url": "ftp://example.com/file"})
        assert r.status_code == 422

    def test_blocked_domain_returns_422(self, client):
        r = client.post("/api/qr/create", json={"url": "https://evil.com/path"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /r/{token}
# ---------------------------------------------------------------------------

class TestRedirect:
    def test_active_token_returns_302(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        r = client.get(f"/r/{token}")
        assert r.status_code == 302
        assert r.headers["location"] == "https://example.com"

    def test_active_redirect_records_scan_event(self, client, db):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.get(f"/r/{token}")
        count = db.query(ScanEvent).filter(ScanEvent.token == token).count()
        assert count == 1

    def test_deleted_token_returns_410(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.delete(f"/api/qr/{token}")
        r = client.get(f"/r/{token}")
        assert r.status_code == 410

    def test_expired_token_returns_410(self, client, db):
        past = datetime.utcnow() - timedelta(seconds=10)
        mapping = UrlMapping(token="exp0001", original_url="https://example.com", expires_at=past)
        db.add(mapping)
        db.commit()
        r = client.get("/r/exp0001")
        assert r.status_code == 410

    def test_nonexistent_token_returns_404(self, client):
        r = client.get("/r/zzz0000")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/qr/{token}
# ---------------------------------------------------------------------------

class TestGetInfo:
    def test_active_token_returns_200(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        r = client.get(f"/api/qr/{token}")
        assert r.status_code == 200
        body = r.json()
        assert body["token"] == token
        assert body["original_url"] == "https://example.com"
        assert body["is_deleted"] is False

    def test_deleted_token_returns_404(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.delete(f"/api/qr/{token}")
        r = client.get(f"/api/qr/{token}")
        assert r.status_code == 404

    def test_nonexistent_token_returns_404(self, client):
        r = client.get("/api/qr/zzz0000")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/qr/{token}
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_url_returns_200(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        r = client.patch(f"/api/qr/{token}", json={"url": "https://updated.com"})
        assert r.status_code == 200
        assert r.json()["original_url"] == "https://updated.com"

    def test_redirect_after_patch_goes_to_new_url(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.get(f"/r/{token}")  # warm cache
        client.patch(f"/api/qr/{token}", json={"url": "https://updated.com"})
        r = client.get(f"/r/{token}")
        assert r.status_code == 302
        assert r.headers["location"] == "https://updated.com"

    def test_set_past_expires_at_causes_410(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        past = (datetime.utcnow() - timedelta(seconds=5)).isoformat()
        client.patch(f"/api/qr/{token}", json={"expires_at": past})
        r = client.get(f"/r/{token}")
        assert r.status_code == 410

    def test_nonexistent_token_returns_404(self, client):
        r = client.patch("/api/qr/zzz0000", json={"url": "https://example.com"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/qr/{token}
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_active_returns_200(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        r = client.delete(f"/api/qr/{token}")
        assert r.status_code == 200

    def test_redirect_after_delete_returns_410(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.get(f"/r/{token}")  # warm cache
        client.delete(f"/api/qr/{token}")
        r = client.get(f"/r/{token}")
        assert r.status_code == 410

    def test_nonexistent_token_returns_404(self, client):
        r = client.delete("/api/qr/zzz0000")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/qr/{token}/image
# ---------------------------------------------------------------------------

class TestImage:
    def test_active_token_returns_png(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        r = client.get(f"/api/qr/{token}/image")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/png")

    def test_nonexistent_token_returns_404(self, client):
        r = client.get("/api/qr/zzz0000/image")
        assert r.status_code == 404

    def test_deleted_token_returns_404(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.delete(f"/api/qr/{token}")
        r = client.get(f"/api/qr/{token}/image")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/qr/{token}/analytics
# ---------------------------------------------------------------------------

class TestAnalytics:
    def test_returns_total_scans_and_scans_by_day(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.get(f"/r/{token}")  # generate one scan event
        r = client.get(f"/api/qr/{token}/analytics")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["total_scans"], int)
        assert body["total_scans"] == 1
        assert isinstance(body["scans_by_day"], list)

    def test_nonexistent_token_returns_404(self, client):
        r = client.get("/api/qr/zzz0000/analytics")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

class TestCacheInvalidation:
    def test_patch_invalidates_stale_cache(self, client):
        token = client.post("/api/qr/create", json={"url": "https://original.com"}).json()["token"]
        client.get(f"/r/{token}")  # warm cache with original URL
        client.patch(f"/api/qr/{token}", json={"url": "https://new.com"})
        r = client.get(f"/r/{token}")
        assert r.status_code == 302
        assert r.headers["location"] == "https://new.com"

    def test_delete_invalidates_stale_cache(self, client):
        token = client.post("/api/qr/create", json={"url": "https://example.com"}).json()["token"]
        client.get(f"/r/{token}")  # warm cache
        client.delete(f"/api/qr/{token}")
        r = client.get(f"/r/{token}")
        assert r.status_code == 410
