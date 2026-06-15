"""
Configuración de SQLAlchemy para el CRM Bayiva.

Usamos SQLite como motor inicial (sin async para mantenerlo simple).
Cuando migren a PostgreSQL, solo cambia DATABASE_URL.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}  # necesario para SQLite + FastAPI
    if settings.database_url.startswith("sqlite")
    else {},
    echo=False,
)


# Activar WAL mode en SQLite para mejor concurrencia
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependencia FastAPI que inyecta una sesión de BD y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Base declarativa
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass
