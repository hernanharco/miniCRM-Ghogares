"""
Esquemas Pydantic para validación de datos de entrada/salida de la API.
Centraliza la validación y la documentación automática (OpenAPI/Swagger).
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models import EstadoPropiedad, Fuente, TipoInmueble


# =============================================================================
# Contacto
# =============================================================================


class ContactoCreate(BaseModel):
    """Esquema para crear/actualizar un contacto."""

    id_ghl: Optional[str] = None
    nombre: str = ""
    email: str = ""
    telefono: str = ""
    precio_max: Optional[float] = None
    zona: Optional[str] = None
    habitaciones: Optional[int] = None
    metros_min: Optional[int] = None
    tipo: Optional[TipoInmueble] = None
    notas: Optional[str] = None
    plazo: Optional[str] = None
    motivacion: Optional[str] = None
    propiedad_interes_id: Optional[int] = None

    @field_validator("precio_max")
    @classmethod
    def precio_positivo(cls, v):
        if v is not None and v < 0:
            raise ValueError("El precio no puede ser negativo")
        return v

    @field_validator("habitaciones", "metros_min")
    @classmethod
    def numeros_positivos(cls, v):
        if v is not None and v < 0:
            raise ValueError("El valor no puede ser negativo")
        return v


class ContactoResponse(BaseModel):
    """Esquema de respuesta para un contacto."""

    id: int
    id_ghl: str
    nombre: str
    email: str
    telefono: str
    precio_max: Optional[float] = None
    zona: Optional[str] = None
    habitaciones: Optional[int] = None
    metros_min: Optional[int] = None
    tipo: Optional[str] = None
    plazo: Optional[str] = None
    motivacion: Optional[str] = None
    propiedad_interes_id: Optional[int] = None
    notas: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# =============================================================================
# Propiedad
# =============================================================================


class PropiedadCreate(BaseModel):
    """Esquema para crear/actualizar una propiedad."""

    id_externo: str
    fuente: Fuente = Fuente.MANUAL
    url: Optional[str] = ""
    titulo: Optional[str] = ""
    precio: float = 0.0
    precio_texto: Optional[str] = ""
    direccion: Optional[str] = ""
    zona: Optional[str] = ""
    municipio: Optional[str] = None
    provincia: Optional[str] = None
    tipo: TipoInmueble = TipoInmueble.OTRO
    metros: Optional[int] = None
    metros_utiles: Optional[int] = None
    habitaciones: Optional[int] = None
    banos: Optional[int] = None
    planta: Optional[str] = None
    ascensor: Optional[bool] = None
    estado_inmueble: str = "desconocido"
    estado: EstadoPropiedad = EstadoPropiedad.DISPONIBLE
    descripcion: Optional[str] = None
    fotos: str = "[]"
    agencia: Optional[str] = None
    fecha_publicacion: Optional[date] = None

    @field_validator("precio")
    @classmethod
    def precio_positivo(cls, v):
        if v < 0:
            raise ValueError("El precio no puede ser negativo")
        return v


class PropiedadResponse(BaseModel):
    """Esquema de respuesta para una propiedad."""

    id: int
    id_externo: str
    fuente: Optional[str] = None
    url: Optional[str] = None
    titulo: Optional[str] = None
    precio: float = 0.0
    precio_texto: Optional[str] = None
    direccion: Optional[str] = None
    zona: Optional[str] = None
    municipio: Optional[str] = None
    provincia: Optional[str] = None
    tipo: Optional[str] = None
    metros: Optional[int] = None
    metros_utiles: Optional[int] = None
    habitaciones: Optional[int] = None
    banos: Optional[int] = None
    planta: Optional[str] = None
    ascensor: Optional[bool] = None
    estado_inmueble: Optional[str] = None
    estado: Optional[str] = None
    descripcion: Optional[str] = None
    agencia: Optional[str] = None
    fecha_publicacion: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# =============================================================================
# Match
# =============================================================================


class MatchResponse(BaseModel):
    """Esquema de respuesta para un match."""

    id: int
    propiedad_id: int
    contacto_id: int
    score: int
    enviado: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# =============================================================================
# Mensajes genéricos
# =============================================================================


class MensajeResponse(BaseModel):
    """Respuesta genérica con mensaje."""

    mensaje: str
    id: Optional[int] = None
