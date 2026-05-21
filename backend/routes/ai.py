"""Analyse IA Claude Sonnet 4.5."""
import os, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException

from database import get_db
from auth import require_auth

router = APIRouter()

SYSTEM = (
    "Tu es un expert en surveillance forestière travaillant pour le Centre de Gestion de Gagnoa "
    "en Côte d'Ivoire. Tu analyses les observations terrain et alertes liées à la déforestation, "
    "à l'agriculture illégale (notamment de cacao), aux feux de brousse et à l'exploitation forestière. "
    "Réponds toujours en français, de manière structurée :\n"
    "1. **Analyse** (synthèse rapide)\n"
    "2. **Niveau de gravité** (faible / moyenne / haute / critique)\n"
    "3. **Causes probables**\n"
    "4. **Recommandations** (actions concrètes)\n"
    "5. **Priorité d'intervention** (1-5, 5 = très urgent)"
)


@router.post("/ai/analyze")
async def analyze(request: Request, db=Depends(get_db)):
    user = require_auth(request)
    body = await request.json()
    text = (body.get("text") or "").strip()
    context = body.get("context")
    if not text:
        raise HTTPException(400, "Texte requis")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        raise HTTPException(500, f"LLM indisponible: {e}")

    chat = LlmChat(
        api_key=os.environ["EMERGENT_LLM_KEY"],
        session_id=f"gestpro-{user['tokenY']}-{uuid.uuid4()}",
        system_message=SYSTEM,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    final_text = f"Contexte: {context}\n\nDescription:\n{text}" if context else text
    try:
        response = await chat.send_message(UserMessage(text=final_text))
    except Exception as e:
        raise HTTPException(502, f"Erreur LLM: {e}")

    aid = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO ai_analyses (id,user_id,input_text,context,response,model) VALUES ($1,$2,$3,$4,$5,'claude-sonnet-4-5')",
        aid, user["tokenY"], text, context, response,
    )
    row = await db.fetchrow("SELECT * FROM ai_analyses WHERE id=$1", aid)
    d = dict(row); d["created_at"] = d["created_at"].isoformat()
    return d


@router.get("/ai/history")
async def history(request: Request, db=Depends(get_db)):
    user = require_auth(request)
    rows = await db.fetch("SELECT * FROM ai_analyses WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50", user["tokenY"])
    out = []
    for r in rows:
        d = dict(r); d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out
