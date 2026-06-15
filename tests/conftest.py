"""
Configuración global de tests.
Usa una base de datos SQLite en memoria para no contaminar la BD real.
"""

import os
import tempfile
from pathlib import Path

import jinja2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# Inicializar Jinja2 para los tests (el lifespan no se ejecuta con TestClient)
_templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"
app.state.jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_templates_dir)),
    autoescape=True,
)

# ---------------------------------------------------------------------------
# Base de datos de prueba (archivo temporal único)
# ---------------------------------------------------------------------------
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")

test_engine = create_engine(
    f"sqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(test_engine, "connect")
def _set_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Crea las tablas antes de cada test y las limpia después."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    """Sobrescribe la dependencia de BD para usar la BD de prueba."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """Cliente HTTP de prueba."""
    return TestClient(app)


@pytest.fixture
def db():
    """Sesión de BD de prueba."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def teardown_module():
    """Limpia el archivo temporal al finalizar."""
    os.close(_db_fd)
    os.unlink(_db_path)


# ---------------------------------------------------------------------------
# Datos de ejemplo
# ---------------------------------------------------------------------------

SAMPLE_PROPIEDAD = {
    "id_externo": "test_001",
    "fuente": "manual",
    "titulo": "Piso de prueba en Centro",
    "precio": 180000.0,
    "zona": "Centro",
    "tipo": "piso",
    "habitaciones": 3,
    "metros": 80,
    "estado": "disponible",
}

SAMPLE_CONTACTO = {
    "id_ghl": "ghl_test_001",
    "nombre": "María García",
    "email": "maria@test.com",
    "telefono": "612345678",
    "precio_max": 200000.0,
    "zona": "Centro",
    "habitaciones": 3,
    "metros_min": 75,
    "tipo": "piso",
    "plazo": "urgente",
    "motivacion": "primera_vivienda",
}
