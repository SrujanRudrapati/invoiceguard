"""Production mode: the built review app at / and the API at /api, one origin and port.

The web app already calls relative /api/... URLs (the Vite dev proxy strips /api), so mounting
the unchanged API under /api serves both from one process.

Run: cd web && npm run build
     uv run uvicorn invoiceguard.serve:create_app --factory --host 0.0.0.0 --port 8000
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from invoiceguard import api
from invoiceguard.config import ROOT

WEB_DIST = ROOT / "web" / "dist"


class MissingWebBuildError(RuntimeError):
    pass


def web_dist() -> Path:
    return Path(os.environ.get("INVOICEGUARD_WEB_DIST", WEB_DIST))


def create_app() -> FastAPI:
    """Factory (uvicorn --factory): importing this module never needs the web build."""
    dist = web_dist()
    if not (dist / "index.html").is_file():
        raise MissingWebBuildError(f"No web build at {dist}. Run: cd web && npm run build")
    app = FastAPI(title="InvoiceGuard")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.mount("/api", api.app)
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app
