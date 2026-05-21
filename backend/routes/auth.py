"""Auth GestPro — JWT cookie httpOnly + sessions flash."""
import bcrypt
import logging
import uuid

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from auth import create_access_token, get_current_user, require_auth

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


@router.get("/connexion", response_class=HTMLResponse)
async def page_connexion(request: Request):
    return templates.TemplateResponse("connexion.html", {
        "request": request,
        "error":   request.session.pop("error", []),
        "success": request.session.pop("success", []),
    })


@router.post("/connexion")
async def post_connexion(
    request: Request,
    email: str = Form(...),
    mp: str = Form(...),
    db=Depends(get_db),
):
    email = (email or "").lower().strip()
    user = await db.fetchrow("SELECT * FROM utilisateurs WHERE email=$1", email)
    if not user:
        request.session["error"] = ["Utilisateur non trouvé."]
        return RedirectResponse("/connexion", status_code=302)

    if not bcrypt.checkpw(mp.encode(), user["mp"].encode()):
        request.session["error"] = ["Mot de passe incorrect."]
        return RedirectResponse("/connexion", status_code=302)

    token_data = {
        "tokenY": user["token_y"], "email": user["email"],
        "full_name": user["full_name"], "role": user["role"],
    }
    access_token = create_access_token(token_data)
    await db.execute("UPDATE utilisateurs SET etat='connecte' WHERE email=$1", email)

    response = RedirectResponse(f"/dashboard/{user['token_y']}", status_code=302)
    response.set_cookie("token", access_token, httponly=True, samesite="lax", max_age=43200, path="/")
    return response


@router.get("/log/deconnecter")
async def deconnecter(request: Request, db=Depends(get_db)):
    user = get_current_user(request)
    if user:
        await db.execute("UPDATE utilisateurs SET etat='deconnecte' WHERE email=$1", user.get("email"))
    response = RedirectResponse("/connexion", status_code=302)
    response.delete_cookie("token", path="/")
    return response


# JSON API endpoints (for Kobo etc.)
@router.post("/api/auth/login")
async def api_login(request: Request, db=Depends(get_db)):
    payload = await request.json()
    email = (payload.get("email") or "").lower().strip()
    mp = payload.get("password") or ""
    user = await db.fetchrow("SELECT * FROM utilisateurs WHERE email=$1", email)
    if not user or not bcrypt.checkpw(mp.encode(), user["mp"].encode()):
        return JSONResponse({"detail": "Email ou mot de passe incorrect"}, status_code=401)
    token_data = {"tokenY": user["token_y"], "email": user["email"],
                  "full_name": user["full_name"], "role": user["role"]}
    access_token = create_access_token(token_data)
    response = JSONResponse({"user": {
        "id": user["token_y"], "email": user["email"], "full_name": user["full_name"],
        "role": user["role"], "active": user["active"],
        "created_at": user["created_at"].isoformat(),
    }, "access_token": access_token})
    response.set_cookie("token", access_token, httponly=True, samesite="lax", max_age=43200, path="/")
    return response


@router.get("/api/auth/me")
async def api_me(request: Request, db=Depends(get_db)):
    user = require_auth(request)
    row = await db.fetchrow("SELECT * FROM utilisateurs WHERE email=$1", user["email"])
    if not row:
        return JSONResponse({"detail": "Non authentifié"}, status_code=401)
    return {
        "id": row["token_y"], "email": row["email"], "full_name": row["full_name"],
        "role": row["role"], "active": row["active"],
        "created_at": row["created_at"].isoformat(),
    }


@router.post("/api/auth/logout")
async def api_logout(request: Request, db=Depends(get_db)):
    user = get_current_user(request)
    if user:
        await db.execute("UPDATE utilisateurs SET etat='deconnecte' WHERE email=$1", user.get("email"))
    response = JSONResponse({"message": "Déconnecté"})
    response.delete_cookie("token", path="/")
    return response
