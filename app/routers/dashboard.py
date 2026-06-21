"""
Rutas del dashboard — estadísticas y resumen para el portal React.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Contacto, EstadoPropiedad, Match, Propiedad
from app.schemas import DashboardStats

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    """Devuelve estadísticas generales para el dashboard."""

    total_propiedades = db.query(Propiedad).count()
    total_contactos = db.query(Contacto).count()
    total_matches = db.query(Match).count()

    propiedades_disponibles = db.query(Propiedad).filter(
        Propiedad.estado == EstadoPropiedad.DISPONIBLE
    ).count()
    propiedades_reservadas = db.query(Propiedad).filter(
        Propiedad.estado == EstadoPropiedad.RESERVADA
    ).count()
    propiedades_vendidas = db.query(Propiedad).filter(
        Propiedad.estado == EstadoPropiedad.VENDIDA
    ).count()

    matches_pendientes = db.query(Match).filter(
        Match.enviado == False  # noqa: E712
    ).count()
    matches_enviados = db.query(Match).filter(
        Match.enviado == True  # noqa: E712
    ).count()

    # Contactos que no tienen ningún match
    contactos_con_match = (
        db.query(Match.contacto_id).distinct().subquery()
    )
    contactos_sin_match = db.query(Contacto).filter(
        Contacto.id.notin_(db.query(contactos_con_match.c.contacto_id))
    ).count()

    return DashboardStats(
        total_propiedades=total_propiedades,
        total_contactos=total_contactos,
        total_matches=total_matches,
        propiedades_disponibles=propiedades_disponibles,
        propiedades_reservadas=propiedades_reservadas,
        propiedades_vendidas=propiedades_vendidas,
        matches_pendientes=matches_pendientes,
        matches_enviados=matches_enviados,
        contactos_sin_match=contactos_sin_match,
    )
