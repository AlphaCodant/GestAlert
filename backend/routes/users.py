"""Gestion utilisateurs (admin)."""
import uuid, bcrypt
from fastapi import APIRouter, Request, Depends, HTTPException

from database import get_db
from auth import require_admin, require_auth

router = APIRouter()


@router.get("/users")
async def list_users(request: Request, db=Depends(get_db)):
    require_admin(request)
    rows = await db.fetch("SELECT token_y AS id, email, full_name, role, active, created_at FROM utilisateurs ORDER BY created_at DESC")
    out = []
    for r in rows:
        d = dict(r); d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        out.append(d)
    return out


@router.post("/auth/register")
async def create_user(request: Request, db=Depends(get_db)):
    require_admin(request)
    d = await request.json()
    email = (d["email"] or "").lower().strip()
    if await db.fetchrow("SELECT id FROM utilisateurs WHERE email=$1", email):
        raise HTTPException(400, "Email déjà utilisé")
    if len(d["password"]) < 6:
        raise HTTPException(400, "Mot de passe trop court")
    hashed = bcrypt.hashpw(d["password"].encode(), bcrypt.gensalt()).decode()
    token_y = uuid.uuid4().hex[:16]
    await db.execute(
        "INSERT INTO utilisateurs (email, mp, full_name, role, token_y) VALUES ($1,$2,$3,$4,$5)",
        email, hashed, d["full_name"], d["role"], token_y,
    )
    return {"id": token_y, "email": email, "full_name": d["full_name"], "role": d["role"]}


@router.delete("/users/{user_id}")
async def del_user(user_id: str, request: Request, db=Depends(get_db)):
    admin = require_admin(request)
    if user_id == admin["tokenY"]:
        raise HTTPException(400, "Impossible de supprimer son propre compte")
    res = await db.execute("DELETE FROM utilisateurs WHERE token_y=$1", user_id)
    if res.endswith("0"):
        raise HTTPException(404, "Utilisateur introuvable")
    return {"message": "Supprimé"}
