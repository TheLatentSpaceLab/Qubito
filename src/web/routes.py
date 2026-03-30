"""Web UI routes serving HTMX-powered HTML pages."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

web_router = APIRouter(prefix="/ui", tags=["web-ui"])


@web_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@web_router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request) -> HTMLResponse:
    """Chat interface page."""
    return templates.TemplateResponse("chat.html", {"request": request})


@web_router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    """Configuration management page."""
    return templates.TemplateResponse("config.html", {"request": request})


@web_router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request) -> HTMLResponse:
    """Logs and observability page."""
    return templates.TemplateResponse("logs.html", {"request": request})


# --- HTMX fragment endpoints ---

@web_router.get("/fragments/status", response_class=HTMLResponse)
async def fragment_status(request: Request) -> HTMLResponse:
    """Status card fragment for HTMX polling."""
    import httpx
    try:
        resp = httpx.get(f"http://127.0.0.1:{request.url.port or 8741}/status", timeout=3)
        data = resp.json()
    except Exception:
        data = {"status": "unreachable", "sessions_count": 0, "uptime_seconds": 0}
    return templates.TemplateResponse("fragments/status.html", {"request": request, "status": data})


@web_router.get("/fragments/sessions", response_class=HTMLResponse)
async def fragment_sessions(request: Request) -> HTMLResponse:
    """Sessions list fragment for HTMX polling."""
    import httpx
    try:
        resp = httpx.get(f"http://127.0.0.1:{request.url.port or 8741}/sessions", timeout=3)
        sessions = resp.json()
    except Exception:
        sessions = []
    return templates.TemplateResponse("fragments/sessions.html", {"request": request, "sessions": sessions})
