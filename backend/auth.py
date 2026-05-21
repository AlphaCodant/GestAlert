"""Auth JWT via cookie httpOnly — pattern GESTREB."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import jwt as pyjwt

SECRET_KEY = os.getenv("SECRET_KEY", "my_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12h


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except pyjwt.PyJWTError:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("token")
    if not token:
        return None
    return decode_token(token)


def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/connexion"})
    return user


def require_admin(request: Request) -> dict:
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accès admin requis")
    return user
