"""
CRM Bayiva — FastAPI Application
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import jinja2
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import AuthMiddleware
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import contactos, match, propiedades, scraper

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: setup al iniciar, cleanup al cerrar
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 50)
    logger.info("CRM Bayiva iniciando...")
    logger.info("=" * 50)

    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas verificadas/creadas")

    # Jinja2 environment (necesario para acceso desde routers)
    templates_dir = Path(__file__).resolve().parent / "templates"
    app.state.jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )

    # Importar datos del scraper existente al arrancar
    try:
        from app.services.importador import importar_desde_scraper

        db = SessionLocal()
        try:
            resultado = importar_desde_scraper(db)
            if resultado.get("importadas", 0) > 0:
                logger.info("✅ Importadas %d propiedades del scraper", resultado["importadas"])
            elif resultado.get("error"):
                logger.warning("⚠️  Import: %s", resultado["error"])
            else:
                logger.info("ℹ️  Import: %d importadas, %d omitidas", resultado.get("importadas", 0), resultado.get("omitidas", 0))
        finally:
            db.close()
    except Exception as e:
        logger.warning("⚠️  No se pudo importar del scraper: %s", e)

    yield

    logger.info("CRM Bayiva detenido")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CRM Bayiva — Grupo Hogares",
    description="CRM interno para gestión de propiedades y matching con contactos de GHL",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Middleware (orden: CORS primero, Auth después) ──────────────
# CORS debe ir primero para que las preflight OPTIONS no requieran auth
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware valida JWT de Supabase en cada request
app.add_middleware(AuthMiddleware)

# Static files (CSS, JS)
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Routers
app.include_router(propiedades.router)
app.include_router(contactos.router)
app.include_router(match.router)
app.include_router(scraper.router)

# ── Healthcheck ────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
def health():
    """Endpoint para healthcheck de Docker. Exento de auth."""
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Helpers para Jinja2
# ---------------------------------------------------------------------------
def _get_jinja_env(app: FastAPI) -> jinja2.Environment:
    """Retorna el Jinja2 environment. Útil para HTMX partials."""
    if not hasattr(app.state, "jinja_env"):
        templates_dir = Path(__file__).resolve().parent / "templates"
        app.state.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )
    return app.state.jinja_env


# ---------------------------------------------------------------------------
# Página principal (Dashboard)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Dashboard principal del CRM."""
    from app.models import Contacto, Match, Propiedad

    db = SessionLocal()
    try:
        total_propiedades = db.query(Propiedad).count()
        disponibles = db.query(Propiedad).filter(Propiedad.estado == "disponible").count()
        reservadas = db.query(Propiedad).filter(Propiedad.estado == "reservada").count()
        vendidas = db.query(Propiedad).filter(Propiedad.estado == "vendida").count()

        total_contactos = db.query(Contacto).count()
        urgentes = db.query(Contacto).filter(Contacto.plazo == "urgente").count()

        total_matches = db.query(Match).count()
        matches_pendientes = db.query(Match).filter(Match.enviado == False).count()

        # Últimos matches
        ultimos_matches = (
            db.query(Match)
            .order_by(Match.created_at.desc())
            .limit(5)
            .all()
        )

        # Últimas propiedades importadas
        ultimas_propiedades = (
            db.query(Propiedad)
            .order_by(Propiedad.created_at.desc())
            .limit(5)
            .all()
        )

        # Contactos urgentes sin match enviado (atención necesaria)
        atencion = (
            db.query(Contacto)
            .filter(Contacto.plazo == "urgente")
            .order_by(Contacto.updated_at.desc())
            .limit(5)
            .all()
        )

        return _get_jinja_env(app).get_template("index.html").render(
            {
                "request": request,
                "total_propiedades": total_propiedades,
                "disponibles": disponibles,
                "reservadas": reservadas,
                "vendidas": vendidas,
                "total_contactos": total_contactos,
                "urgentes": urgentes,
                "total_matches": total_matches,
                "matches_pendientes": matches_pendientes,
                "ultimos_matches": ultimos_matches,
                "ultimas_propiedades": ultimas_propiedades,
                "atencion": atencion,
            }
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
