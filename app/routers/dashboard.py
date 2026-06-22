"""
Rutas del dashboard — estadísticas y resumen para el portal React.
Incluye listas de últimos matches, últimas propiedades y contactos urgentes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Contacto, EstadoPropiedad, Match, Propiedad
from app.schemas import DashboardStats

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard")
def dashboard_stats(db: Session = Depends(get_db)):
    """Devuelve estadísticas generales + listas recientes para el dashboard."""

    total_propiedades = db.query(Propiedad).count()
    total_contactos = db.query(Contacto).count()
    total_matches = db.query(Match).count()

    disponibles = db.query(Propiedad).filter(
        Propiedad.estado == EstadoPropiedad.DISPONIBLE
    ).count()
    reservadas = db.query(Propiedad).filter(
        Propiedad.estado == EstadoPropiedad.RESERVADA
    ).count()
    vendidas = db.query(Propiedad).filter(
        Propiedad.estado == EstadoPropiedad.VENDIDA
    ).count()

    matches_pendientes = db.query(Match).filter(
        Match.enviado == False  # noqa: E712
    ).count()
    matches_enviados = db.query(Match).filter(
        Match.enviado == True  # noqa: E712
    ).count()

    urgentes = db.query(Contacto).filter(
        Contacto.plazo == "urgente"
    ).count()

    # Contactos sin match
    contactos_con_match = (
        db.query(Match.contacto_id).distinct().subquery()
    )
    contactos_sin_match = db.query(Contacto).filter(
        Contacto.id.notin_(db.query(contactos_con_match.c.contacto_id))
    ).count()

    # Últimos matches (con joins a propiedad y contacto)
    ultimos_matches = (
        db.query(Match)
        .options(joinedload(Match.propiedad), joinedload(Match.contacto))
        .order_by(Match.created_at.desc())
        .limit(5)
        .all()
    )

    # Últimas propiedades
    ultimas_propiedades = (
        db.query(Propiedad)
        .order_by(Propiedad.created_at.desc())
        .limit(5)
        .all()
    )

    # Contactos urgentes para atención
    atencion = (
        db.query(Contacto)
        .filter(Contacto.plazo == "urgente")
        .order_by(Contacto.updated_at.desc())
        .limit(5)
        .all()
    )

    def _serializar_match(m):
        return {
            "id": m.id,
            "propiedad_id": m.propiedad_id,
            "contacto_id": m.contacto_id,
            "score": m.score,
            "enviado": m.enviado,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "propiedad": {
                "id": m.propiedad.id,
                "titulo": m.propiedad.titulo,
                "precio": m.propiedad.precio,
                "zona": m.propiedad.zona,
            } if m.propiedad else None,
            "contacto": {
                "id": m.contacto.id,
                "nombre": m.contacto.nombre,
            } if m.contacto else None,
        }

    def _serializar_propiedad(p):
        return {
            "id": p.id,
            "titulo": p.titulo,
            "precio": p.precio,
            "zona": p.zona,
            "tipo": p.tipo.value if p.tipo else None,
            "estado": p.estado.value if p.estado else None,
        }

    def _serializar_contacto(c):
        return {
            "id": c.id,
            "nombre": c.nombre,
            "zona": c.zona,
            "precio_max": c.precio_max,
            "plazo": c.plazo,
        }

    return {
        "total_propiedades": total_propiedades,
        "total_contactos": total_contactos,
        "total_matches": total_matches,
        "propiedades_disponibles": disponibles,
        "propiedades_reservadas": reservadas,
        "propiedades_vendidas": vendidas,
        "matches_pendientes": matches_pendientes,
        "matches_enviados": matches_enviados,
        "contactos_sin_match": contactos_sin_match,
        "urgentes": urgentes,
        "ultimos_matches": [_serializar_match(m) for m in ultimos_matches],
        "ultimas_propiedades": [_serializar_propiedad(p) for p in ultimas_propiedades],
        "atencion": [_serializar_contacto(c) for c in atencion],
    }
