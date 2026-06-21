"""
Modelos de datos del CRM Bayiva.

Reflejan el dominio: Propiedades (desde scrapers/carga manual),
Contactos (desde GHL), y Matches (relación entre ambos).
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

# ---------------------------------------------------------------------------
# Enums compatibles con los del scraper (src/models.py)
# ---------------------------------------------------------------------------

import enum


class TipoInmueble(str, enum.Enum):
    PISO = "piso"
    CASA = "casa"
    ATICO = "atico"
    DUPLEX = "duplex"
    LOCAL = "local"
    OFICINA = "oficina"
    NAVE = "nave"
    GARAJE = "garaje"
    TRASTERO = "trastero"
    OTRO = "otro"


class EstadoPropiedad(str, enum.Enum):
    DISPONIBLE = "disponible"
    RESERVADA = "reservada"
    VENDIDA = "vendida"
    DESCARTA = "descartada"


class Fuente(str, enum.Enum):
    FOTOCASA = "fotocasa"
    IDEALISTA = "idealista"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Propiedad
# ---------------------------------------------------------------------------


class Propiedad(Base):
    """Propiedad inmobiliaria, venga de scraper o carga manual."""

    __tablename__ = "propiedades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_externo = Column(String(100), nullable=False)
    fuente = Column(SAEnum(Fuente), nullable=False, default=Fuente.MANUAL)
    url = Column(Text, default="")

    # Datos principales
    titulo = Column(String(300), default="")
    precio = Column(Float, default=0.0)
    precio_texto = Column(String(50), default="")

    # Ubicación
    direccion = Column(String(300), default="")
    zona = Column(String(100), default="")
    municipio = Column(String(100), nullable=True)
    provincia = Column(String(100), nullable=True)

    # Características
    tipo = Column(SAEnum(TipoInmueble), default=TipoInmueble.OTRO)
    metros = Column(Integer, nullable=True)
    metros_utiles = Column(Integer, nullable=True)
    habitaciones = Column(Integer, nullable=True)
    banos = Column(Integer, nullable=True)
    planta = Column(String(20), nullable=True)
    ascensor = Column(Boolean, nullable=True)
    estado_inmueble = Column(String(30), default="desconocido")

    # Estado en el CRM
    estado = Column(SAEnum(EstadoPropiedad), default=EstadoPropiedad.DISPONIBLE)

    # Metadata
    descripcion = Column(Text, nullable=True)
    fotos = Column(Text, default="[]")  # JSON array de URLs
    agencia = Column(String(200), nullable=True)
    fecha_publicacion = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relaciones
    matches = relationship("Match", back_populates="propiedad", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Propiedad {self.id}: {self.titulo} - {self.precio}€>"


# ---------------------------------------------------------------------------
# Contacto (desde GHL)
# ---------------------------------------------------------------------------


class Contacto(Base):
    """Contacto/lead que busca vivienda. Sincronizado desde GHL."""

    __tablename__ = "contactos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_ghl = Column(String(100), unique=True, nullable=False)
    nombre = Column(String(200), default="")
    email = Column(String(200), default="")
    telefono = Column(String(50), default="")

    # Preferencias de búsqueda
    precio_max = Column(Float, nullable=True)
    zona = Column(String(100), nullable=True)
    habitaciones = Column(Integer, nullable=True)
    metros_min = Column(Integer, nullable=True)
    tipo = Column(SAEnum(TipoInmueble), nullable=True)

    # Intención de compra (mapping GHL)
    plazo = Column(String(50), nullable=True)        # urgente, 1-3 meses, 3-6 meses, 6-12 meses, sin_prisa
    motivacion = Column(String(100), nullable=True)  # primera_vivienda, inversion, ampliacion, cambio_zona, etc.

    # Relación directa con una propiedad específica (no vía matching)
    propiedad_interes_id = Column(Integer, ForeignKey("propiedades.id"), nullable=True)

    # Metadata
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relaciones
    matches = relationship("Match", back_populates="contacto", cascade="all, delete-orphan")
    propiedad_interes = relationship("Propiedad", foreign_keys=[propiedad_interes_id])

    def __repr__(self):
        return f"<Contacto {self.id}: {self.nombre}>"


# ---------------------------------------------------------------------------
# Match (propiedad <-> contacto)
# ---------------------------------------------------------------------------


class EtapaPipeline(str, enum.Enum):
    """Etapas del pipeline comercial."""
    NUEVO = "nuevo"
    CONTACTADO = "contactado"
    NEGOCIACION = "negociacion"
    CERRADO = "cerrado"
    PERDIDO = "perdido"


class Match(Base):
    """Resultado del matching entre un contacto y una propiedad."""

    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    propiedad_id = Column(Integer, ForeignKey("propiedades.id"), nullable=False)
    contacto_id = Column(Integer, ForeignKey("contactos.id"), nullable=False)
    score = Column(Integer, default=0)  # 0-100
    enviado = Column(Boolean, default=False)  # ¿ya se notificó al contacto?
    etapa = Column(String(20), default=EtapaPipeline.NUEVO.value)  # pipeline comercial
    created_at = Column(DateTime, server_default=func.now())

    propiedad = relationship("Propiedad", back_populates="matches")
    contacto = relationship("Contacto", back_populates="matches")

    def __repr__(self):
        return f"<Match {self.id}: Prop {self.propiedad_id} ↔ Cont {self.contacto_id} ({self.score}%)>"
