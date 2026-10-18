import json

import pytest
import requests
from sqlalchemy import select

from sentinela.extensions import db
from sentinela.models import Camera, CameraHealthEvent
from sentinela.services import gateway
from test_inventory import inventory, post


class Response:
    def __init__(self, data, status=200):
        self.status_code, self.data = status, data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def iter_content(self, chunk_size):
        yield self.data


@pytest.fixture
def real_camera(app, inventory):
    app.config.update(MEDIA_GATEWAY_HLS_URL="https://media.example.test", MEDIA_GATEWAY_API_URL="https://api.example.test",
                      MEDIA_GATEWAY_ALLOWED_HOSTS=["media.example.test", "api.example.test"])
    with app.app_context():
        camera = db.session.get(Camera, inventory["cameras"][0])
        camera.protocol = "rtsp"; camera.gateway_path = "authorized-camera"; db.session.commit()
        return camera.id


def test_gateway_probe_and_segment_relay_preserve_verification(app, client, login, real_camera, monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response(json.dumps({"ready": True}).encode() if "/v3/paths/" in url else b"segment-content")
    monkeypatch.setattr(gateway.requests, "get", get)
    login()
    assert post(client, f"/cameras/{real_camera}/check").status_code == 302
    assert client.get(f"/cameras/{real_camera}/status").json["status"] == "online"
    response = client.get(f"/monitoring/{real_camera}/media/segment0.mp4")
    assert response.data == b"segment-content"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.content_type == "video/mp4"
    assert calls[0][0] == "https://api.example.test/v3/paths/get/org-1--authorized-camera"
    assert calls[1][0] == "https://media.example.test/org-1--authorized-camera/segment0.mp4"
    for _, options in calls:
        assert options["allow_redirects"] is False
        assert options["timeout"] == (3, 8)
        assert options.get("verify", True) is not False
        assert "proxies" not in options


@pytest.mark.parametrize("status, code", [(401, "gateway_auth_failed"), (403, "gateway_auth_failed"), (302, "gateway_unavailable"), (404, "source_unavailable"), (500, "gateway_unavailable")])
def test_gateway_errors_are_minimized(client, login, real_camera, monkeypatch, status, code):
    monkeypatch.setattr(gateway.requests, "get", lambda *args, **kwargs: Response(b"rtsp://user:private-secret@internal-ip/path", status))
    login()
    response = client.get(f"/monitoring/{real_camera}/media/index.m3u8")
    assert response.status_code == 502
    assert response.json == {"error": code}
    assert "private-secret" not in response.text


@pytest.mark.parametrize("exception, expected", [(requests.Timeout("private-url"), "gateway_timeout"), (requests.exceptions.SSLError("private-url"), "gateway_unreachable")])
def test_timeout_and_tls_fail_closed(client, login, real_camera, monkeypatch, exception, expected):
    def fail(*args, **kwargs):
        raise exception
    monkeypatch.setattr(gateway.requests, "get", fail)
    login()
    response = client.get(f"/monitoring/{real_camera}/media/index.m3u8")
    assert response.status_code in {502, 504}
    assert response.json["error"] == expected
    assert "private-url" not in response.text
    assert post(client, f"/cameras/{real_camera}/check").status_code == 302
    assert client.get(f"/cameras/{real_camera}/status").json["status"] == "unknown"


@pytest.mark.parametrize("url", ["http://media.example.test", "https://evil.example", "https://user:pass@media.example.test", "https://media.example.test:9999", "https://media.example.test/path", "https://media.example.test?x=1", "https://127.0.0.1", "https://169.254.169.254"])
def test_only_explicit_https_gateway_destinations_are_usable(app, client, login, real_camera, monkeypatch, url):
    app.config["MEDIA_GATEWAY_HLS_URL"] = url
    app.config["MEDIA_GATEWAY_ALLOWED_HOSTS"] += ["127.0.0.1", "169.254.169.254"]
    def forbidden(*args, **kwargs):
        raise AssertionError("Network must not be used for invalid destination")
    monkeypatch.setattr(gateway.requests, "get", forbidden)
    login()
    response = client.get(f"/monitoring/{real_camera}/media/index.m3u8")
    assert response.status_code == 503


def test_manifest_rewrites_every_media_uri(client, login, real_camera, monkeypatch):
    manifest = b'#EXTM3U\n#EXT-X-VERSION:7\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:2.0,\nsegment0.mp4\n'
    monkeypatch.setattr(gateway.requests, "get", lambda *args, **kwargs: Response(manifest))
    login()
    response = client.get(f"/monitoring/{real_camera}/media/index.m3u8")
    assert response.status_code == 200
    assert f'URI="/monitoring/{real_camera}/media/init.mp4"' in response.text
    assert f'/monitoring/{real_camera}/media/segment0.mp4' in response.text
    assert "example.test" not in response.text


@pytest.mark.parametrize("line", ["https://evil.example/media.ts", "//evil.example/media.ts", "../media.ts", "%2e%2e.ts", "media.ts?token=secret", '#EXT-X-MAP:URI="../secret.mp4"', '#EXT-X-MAP:URI="https://evil.example/a.mp4"', '#EXT-X-KEY:METHOD=AES-128,URI="key"', '#EXT-X-PART:DURATION=0.2,URI="part.mp4"', '#EXT-X-SESSION-DATA:VALUE="rtsp://user:secret@camera"'])
def test_unsafe_or_unsupported_manifests_are_rejected(client, login, real_camera, monkeypatch, line):
    monkeypatch.setattr(gateway.requests, "get", lambda *args, **kwargs: Response(("#EXTM3U\n" + line + "\n").encode()))
    login()
    response = client.get(f"/monitoring/{real_camera}/media/index.m3u8")
    assert response.status_code == 502
    assert "evil.example" not in response.text
    assert "rtsp://" not in response.text


def test_response_limits_and_invalid_gateway_json(client, login, real_camera, monkeypatch):
    monkeypatch.setattr(gateway.requests, "get", lambda *args, **kwargs: Response(b"x" * (256 * 1024 + 1)))
    login()
    response = client.get(f"/monitoring/{real_camera}/media/index.m3u8")
    assert response.json == {"error": "gateway_response_too_large"}
    monkeypatch.setattr(gateway.requests, "get", lambda *args, **kwargs: Response(b"not-json"))
    assert post(client, f"/cameras/{real_camera}/check").status_code == 302
    assert client.get(f"/cameras/{real_camera}/status").json["status"] == "unknown"


def test_media_requires_session_and_rejects_arbitrary_query(client, login, real_camera, monkeypatch):
    assert client.get(f"/monitoring/{real_camera}/media/segment0.mp4").status_code == 302
    login()
    assert client.get(f"/monitoring/{real_camera}/media/segment0.mp4?url=https://evil.example").status_code == 404
    assert client.get(f"/monitoring/{real_camera}/media/not-allowed.html").status_code == 404


def test_reconnection_updates_history_and_camera_state(app, client, login, real_camera, monkeypatch):
    login()
    ready = [False]
    monkeypatch.setattr(gateway.requests, "get", lambda *args, **kwargs: Response(json.dumps({"ready": ready[0]}).encode()))
    assert post(client, f"/cameras/{real_camera}/check").status_code == 302
    with app.app_context():
        camera = db.session.get(Camera, real_camera)
        assert camera.connection_status == "offline"
        camera.last_checked_at = None; db.session.commit()
    ready[0] = True
    assert post(client, f"/cameras/{real_camera}/check").status_code == 302
    with app.app_context():
        assert db.session.get(Camera, real_camera).connection_status == "online"
        assert len(db.session.scalars(select(CameraHealthEvent).where(CameraHealthEvent.camera_id == real_camera)).all()) == 2


def test_modern_gateway_online_state_has_priority_over_fallback(client, login, real_camera, monkeypatch):
    monkeypatch.setattr(gateway.requests, "get", lambda *args, **kwargs: Response(b'{"online":false,"ready":true,"available":true}'))
    login()
    assert post(client, f"/cameras/{real_camera}/check").status_code == 302
    assert client.get(f"/cameras/{real_camera}/status").json["status"] == "offline"


def test_gateway_namespace_cannot_be_changed_by_camera_reference(app, client, login, real_camera, monkeypatch):
    with app.app_context():
        camera=db.session.get(Camera,real_camera); camera.gateway_path="org-2--private"; db.session.commit()
    seen=[]
    def get(url, **kwargs):
        seen.append(url)
        return Response(b"controlled-segment")
    monkeypatch.setattr(gateway.requests,"get",get)
    login()
    assert client.get(f"/monitoring/{real_camera}/media/test.mp4").status_code == 200
    assert seen == ["https://media.example.test/org-1--org-2--private/test.mp4"]
