"""Production mode: built web app at /, API at /api, /health, one origin. Raw ASGI calls
(no httpx in the stack)."""

import asyncio
import json

import pytest

from invoiceguard import serve


def get(app, path: str) -> tuple[int, bytes]:
    """Minimal ASGI GET; returns (status, body)."""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
             "root_path": "", "query_string": b"", "headers": [(b"host", b"test")],
             "server": ("test", 80), "client": ("test", 1)}
    sent: list[dict] = []

    async def run() -> None:
        done, requested = asyncio.Event(), False

        async def receive() -> dict:  # request once; then disconnect after the response
            nonlocal requested
            if not requested:
                requested = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await done.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            sent.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                done.set()

        await app(scope, receive, send)

    asyncio.run(asyncio.wait_for(run(), timeout=10))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


@pytest.fixture
def prod_app(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>InvoiceGuard</title>")
    monkeypatch.setenv("INVOICEGUARD_WEB_DIST", str(dist))
    monkeypatch.setenv("INVOICEGUARD_DB", str(tmp_path / "empty.sqlite3"))
    return serve.create_app()


def test_health_is_ok(prod_app):
    assert get(prod_app, "/health") == (200, b'{"status":"ok"}')


def test_root_serves_the_built_web_app(prod_app):
    status, body = get(prod_app, "/")
    assert status == 200 and b"<title>InvoiceGuard</title>" in body


def test_api_is_mounted_under_api_on_the_same_app(prod_app):
    status, body = get(prod_app, "/api/status")
    assert status == 200 and json.loads(body)["systems"] == []


def test_missing_web_build_fails_at_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("INVOICEGUARD_WEB_DIST", str(tmp_path / "nope"))
    with pytest.raises(serve.MissingWebBuildError, match="npm run build"):
        serve.create_app()
