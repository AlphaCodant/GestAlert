"""Pages Jinja2 (rendu HTML)."""
import logging
import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from auth import require_auth, require_admin, get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


def _ctx(request, user, **extra):
    return {"request": request, "user": user, **extra}


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if get_current_user(request):
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/accueil", status_code=302)


@router.get("/accueil", response_class=HTMLResponse)
async def page_accueil(request: Request):
    return templates.TemplateResponse("accueil.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
async def page_dashboard_default(request: Request):
    user = require_auth(request)
    return RedirectResponse(f"/dashboard/{user['tokenY']}", status_code=302)


@router.get("/dashboard/{id}", response_class=HTMLResponse)
async def page_dashboard(request: Request, id: str, db=Depends(get_db)):
    user = require_auth(request)
    return templates.TemplateResponse("dashboard.html", _ctx(request, user))


@router.get("/alertes", response_class=HTMLResponse)
async def page_alertes(request: Request):
    user = require_auth(request)
    return templates.TemplateResponse("alertes.html", _ctx(request, user))


@router.get("/observations", response_class=HTMLResponse)
async def page_observations(request: Request):
    user = require_auth(request)
    return templates.TemplateResponse("observations.html", _ctx(request, user))


@router.get("/drones", response_class=HTMLResponse)
async def page_drones(request: Request):
    user = require_auth(request)
    return templates.TemplateResponse("drones.html", _ctx(request, user))


@router.get("/predictions", response_class=HTMLResponse)
async def page_predictions(request: Request):
    user = require_auth(request)
    return templates.TemplateResponse("predictions.html", _ctx(request, user))


@router.get("/gee", response_class=HTMLResponse)
async def page_gee(request: Request):
    user = require_auth(request)
    return templates.TemplateResponse("gee.html", _ctx(request, user))


@router.get("/ai", response_class=HTMLResponse)
async def page_ai(request: Request):
    user = require_auth(request)
    return templates.TemplateResponse("ai.html", _ctx(request, user))


@router.get("/kobo", response_class=HTMLResponse)
async def page_kobo(request: Request):
    user = require_auth(request)
    webhook = os.getenv("PUBLIC_BASE_URL") or ""
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    if forwarded_host:
        webhook = f"{forwarded_proto}://{forwarded_host}"
    return templates.TemplateResponse("kobo.html", _ctx(request, user,
        webhook_url=f"{webhook}/api/kobo/webhook",
        kobo_token=os.getenv("KOBO_WEBHOOK_SECRET", ""),
    ))


@router.get("/forets", response_class=HTMLResponse)
async def page_forets(request: Request):
    user = require_auth(request)
    return templates.TemplateResponse("forets.html", _ctx(request, user))


@router.get("/utilisateurs", response_class=HTMLResponse)
async def page_utilisateurs(request: Request):
    user = require_admin(request)
    return templates.TemplateResponse("utilisateurs.html", _ctx(request, user))
