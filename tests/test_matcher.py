"""
Tests para el algoritmo de matching.
"""

import pytest

from app.models import Contacto, Propiedad
from app.services.matcher import calcular_score
from app.models import EstadoPropiedad, Fuente, TipoInmueble


@pytest.fixture
def contacto_base():
    return Contacto(
        precio_max=200000,
        zona="Centro",
        habitaciones=3,
        metros_min=80,
    )


@pytest.fixture
def propiedad_base():
    return Propiedad(
        id_externo="test",
        precio=180000,
        zona="Centro",
        habitaciones=3,
        metros=85,
        estado=EstadoPropiedad.DISPONIBLE,
        tipo=TipoInmueble.PISO,
    )


def test_match_perfecto(contacto_base, propiedad_base):
    """100% si todos los criterios coinciden exactamente."""
    score = calcular_score(contacto_base, propiedad_base)
    assert score == 100, f"Esperaba 100, obtuve {score}"


def test_match_precio_excedido(contacto_base, propiedad_base):
    """Precio sobrepasa el máximo → score menor."""
    propiedad_base.precio = 300000
    score = calcular_score(contacto_base, propiedad_base)
    assert score < 100
    assert score > 0


def test_match_zona_diferente(contacto_base, propiedad_base):
    """Zona diferente → penalización."""
    propiedad_base.zona = "Extrarradio"
    score = calcular_score(contacto_base, propiedad_base)
    assert score < 100


def test_match_sin_contacto():
    """Sin preferencias del contacto → score 0."""
    c = Contacto()
    p = Propiedad(id_externo="test", precio=100000, zona="Centro")
    score = calcular_score(c, p)
    assert score == 0


def test_plazo_urgente_suma_puntos(contacto_base, propiedad_base):
    """Plazo 'urgente' suma puntos si la propiedad está disponible."""
    # Usar una propiedad que NO sea match perfecto para ver el bonus
    propiedad_base.zona = "OtraZona"
    propiedad_base.metros = 50  # menos del mínimo

    contacto_base.plazo = "urgente"
    score_con_urgencia = calcular_score(contacto_base, propiedad_base)

    contacto_base.plazo = None
    score_sin_urgencia = calcular_score(contacto_base, propiedad_base)

    assert score_con_urgencia > score_sin_urgencia


def test_motivacion_primera_vivienda_piso(contacto_base, propiedad_base):
    """Primera vivienda + tipo piso → bonus."""
    contacto_base.motivacion = "primera_vivienda"
    score = calcular_score(contacto_base, propiedad_base)
    assert score > 0


def test_motivacion_inversion(contacto_base, propiedad_base):
    """Inversión da un bonus base."""
    contacto_base.motivacion = "inversion"
    score = calcular_score(contacto_base, propiedad_base)
    assert score > 0
