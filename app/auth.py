"""
Autenticación JWT para CRM Bayiva.
Valida tokens de Supabase (portal.bayiva.com) usando el JWT secret compartido.
"""

import logging

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Middleware de autenticación
# ---------------------------------------------------------------------------

EXEMPT_PATHS = {"/health"}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware que valida el JWT de Supabase en cada request.

    El token se puede enviar de dos formas:
      1. Header Authorization: Bearer <token>
      2. Query param: ?token=<token>  (para el iframe en la carga inicial)

    Los paths en EXEMPT_PATHS no requieren autenticación.
    """

    async def dispatch(self, request: Request, call_next):
        # Paths exentos (healthcheck de Docker)
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Intentar obtener el token
        token = _extract_token(request)

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
            # Guardar el token para que los templates puedan usarlo
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

        return await call_next(request)


def _extract_token(request: Request) -> str | None:
    """Extrae el JWT del header Authorization o del query param ?token=."""
    # 1. Header Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]

    # 2. Query param ?token=... (para iframe)
    token = request.query_params.get("token")
    if token:
        return token

    # 3. Cookie (para futura expansión)
    # token = request.cookies.get("sb-token")
    # if token:
    #     return token

    return None
