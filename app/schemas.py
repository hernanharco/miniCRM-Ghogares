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
    telefono_contacto: Optional[str] = None

    @field_validator("precio")
    @classmethod
    def precio_positivo(cls, v):
        if v < 0:
            raise ValueError("El precio no puede ser negativo")
        return v


class PropiedadUpdate(BaseModel):
    """Esquema para actualizar parcialmente una propiedad."""

    estado: Optional[EstadoPropiedad] = None
    titulo: Optional[str] = None
    precio: Optional[float] = None
    descripcion: Optional[str] = None
    agencia: Optional[str] = None


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
    fotos: list[str] = []
    agencia: Optional[str] = None
    telefono_contacto: Optional[str] = None
    fecha_publicacion: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("fotos", mode="before")
    @classmethod
    def fotos_json_a_lista(cls, v):
        """Convierte el string JSON '["url"]' a lista ['url']."""
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []


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


# =============================================================================
# Paginación
# =============================================================================


class PaginatedResponse(BaseModel):
    """Respuesta paginada genérica."""

    items: list
    total: int
    page: int
    limit: int
    total_pages: int


# =============================================================================
# Dashboard
# =============================================================================


class DashboardStats(BaseModel):
    """Estadísticas para el dashboard."""

    total_propiedades: int = 0
    total_contactos: int = 0
    total_matches: int = 0
    propiedades_disponibles: int = 0
    propiedades_reservadas: int = 0
    propiedades_vendidas: int = 0
    matches_pendientes: int = 0
    matches_enviados: int = 0
    contactos_sin_match: int = 0
