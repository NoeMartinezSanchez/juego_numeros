import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from backend.db import guardar_usuario, inicializar_bd, obtener_usuario
from backend.models import UsuarioResponse

BASE_DIR = Path(__file__).resolve().parent.parent

for ruta_env in (BASE_DIR / ".env", BASE_DIR / ".venv" / ".env"):
    if ruta_env.exists():
        load_dotenv(ruta_env)
        break

SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_hex(32)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", PUBLIC_BASE_URL + "/api/auth/callback"
)

oauth = OAuth()


def _configuracion_completa():
    return bool(
        os.getenv("GOOGLE_CLIENT_ID")
        and os.getenv("GOOGLE_CLIENT_SECRET")
        and os.getenv("SESSION_SECRET")
    )


if _configuracion_completa():
    oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@asynccontextmanager
async def _lifespan(app):
    await inicializar_bd()
    yield


router = APIRouter(lifespan=_lifespan)


def _error_configuracion():
    return JSONResponse(
        status_code=500,
        content={"error": "Configuración OAuth incompleta"},
    )


async def usuario_actual(request: Request):
    usuario_id = request.session.get("usuario_id")
    email = request.session.get("email")
    if not usuario_id or not email:
        raise HTTPException(status_code=401, detail="No autenticado")
    return {"id": usuario_id, "email": email}


@router.get("/login")
async def login(request: Request):
    if not _configuracion_completa():
        return _error_configuracion()
    try:
        return await oauth.google.authorize_redirect(request, REDIRECT_URI)
    except OAuthError:
        return RedirectResponse(url=FRONTEND_URL + "?auth=error", status_code=302)
    except Exception:
        return RedirectResponse(url=FRONTEND_URL + "?auth=error", status_code=302)


@router.get("/callback")
async def callback(request: Request):
    if not _configuracion_completa():
        return _error_configuracion()
    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo") or {}
        google_sub = userinfo.get("sub")
        email = userinfo.get("email")
        nombre = userinfo.get("name")
        if not google_sub or not email:
            return RedirectResponse(url=FRONTEND_URL + "?auth=error", status_code=302)
        usuario = await guardar_usuario(google_sub, email, nombre)
        request.session["usuario_id"] = usuario["id"]
        request.session["email"] = usuario["email"]
        return RedirectResponse(url=FRONTEND_URL, status_code=302)
    except OAuthError:
        return RedirectResponse(url=FRONTEND_URL + "?auth=error", status_code=302)
    except Exception:
        return RedirectResponse(url=FRONTEND_URL + "?auth=error", status_code=302)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=UsuarioResponse)
async def me(request: Request):
    usuario_id = request.session.get("usuario_id")
    email = request.session.get("email")
    if not usuario_id or not email:
        raise HTTPException(status_code=401, detail="No autenticado")
    usuario = await obtener_usuario(usuario_id)
    if usuario is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="No autenticado")
    return UsuarioResponse(
        id=usuario["id"],
        email=usuario["email"],
        nombre=usuario["nombre"],
    )
