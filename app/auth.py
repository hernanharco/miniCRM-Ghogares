"""
Autenticación JWT para CRM Bayiva.
Valida tokens de Supabase (portal.bayiva.com) usando el JWT secret compartido.
El token se persiste en una cookie httpOnly para navegación normal (sidebar).
"""

import logging
from datetime import timedelta

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Middleware de autenticación
# ---------------------------------------------------------------------------

EXEMPT_PATHS = {"/health", "/api/webhook/ghl"}
COOKIE_NAME = "token"


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware que valida el JWT de Supabase en cada request.

    El token se puede recibir de tres formas (por orden de prioridad):
      1. Header Authorization: Bearer <token>  (HTMX requests)
      2. Cookie "token"  (navegación normal + refresh de página)
      3. Query param: ?token=<token>  (carga inicial del iframe)

    Cuando el token viene por query param (carga inicial), se persiste
    en una cookie httpOnly para navegaciones posteriores.
    """

    async def dispatch(self, request: Request, call_next):
        # CORS preflight y healthcheck pasan sin autenticación
        if request.method == "OPTIONS" or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Modo desarrollo: si no hay JWT secret configurado, skip auth
        if not settings.supabase_jwt_secret:
            return await call_next(request)

        # Intentar obtener el token
        token = _extract_token(request)
        token_source = _token_source(request)

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token de autenticación requerido"},
            )

        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["aud", "exp", "sub"]},
            )
            request.state.user = payload
            request.state.token = token
        except jwt.ExpiredSignatureError:
            logger.warning("Token expirado: %s", request.client)
            return JSONResponse(
                status_code=401,
                content={"detail": "Token expirado. Inicia sesión nuevamente."},
            )
        except jwt.InvalidAudienceError:
            logger.warning("Audiencia inválida en token: %s", request.client)
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido: audiencia incorrecta"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning("Token inválido (%s): %s", e, request.client)
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido"},
            )

        # Procesar la request
        response = await call_next(request)

        # Si el token vino por query param (carga inicial del iframe),
        # persitirlo en una cookie para navegaciones posteriores
        if token_source == "query" and isinstance(response, Response):
            response.set_cookie(
                key=COOKIE_NAME,
                value=token,
                max_age=3600,           # 1 hora (match con JWT exp)
                httponly=True,
                secure=True,
                samesite="lax",
                path="/",
            )

        return response


def _extract_token(request: Request) -> str | None:
    """Extrae el JWT de header, cookie o query param."""
    # 1. Header Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]

    # 2. Cookie "token" (navegación normal)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token

    # 3. Query param ?token=... (carga inicial iframe)
    token = request.query_params.get("token")
    if token:
        return token

    return None


def _token_source(request: Request) -> str | None:
    """Identifica de dónde se obtuvo el token (para decidir si setear cookie)."""
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return "header"
    if request.cookies.get(COOKIE_NAME):
        return "cookie"
    if request.query_params.get("token"):
        return "query"
    return None
