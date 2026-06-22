"""
Rutas de matching entre contactos y propiedades.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from sqlalchemy import or_

from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models import Contacto, Match, Propiedad
from app.services.matcher import matchear_contacto, matchear_todos

router = APIRouter(tags=["match"])


# =========================================================================
# API JSON
# =========================================================================


@router.get("/api/match/{contacto_id}")
def match_contacto_api(contacto_id: int, db: Session = Depends(get_db)):
    """Ejecuta matching para un contacto. Devuelve JSON con resultados."""
    resultados = matchear_contacto(db, contacto_id)
    return {"contacto_id": contacto_id, "total": len(resultados), "resultados": resultados}


@router.post("/api/match/todos")
def match_todos_api(db: Session = Depends(get_db)):
    """Ejecuta matching para todos los contactos (batch)."""
    resultados = matchear_todos(db)
    return {"total": len(resultados), "resultados": resultados}


@router.get("/api/matches")
def listar_matches_api(
    contacto_id: Optional[int] = Query(None),
    score_min: Optional[int] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    """Lista matches existentes con datos de propiedad y contacto."""
    query = db.query(Match).options(
        joinedload(Match.propiedad),
        joinedload(Match.contacto),
    )

    if contacto_id:
        query = query.filter(Match.contacto_id == contacto_id)
    if score_min is not None:
        query = query.filter(Match.score >= score_min)

    matches = query.order_by(desc(Match.score)).limit(limit).all()

    return [
        {
            "id": m.id,
            "propiedad_id": m.propiedad_id,
            "contacto_id": m.contacto_id,
            "score": m.score,
            "enviado": m.enviado,
            "etapa": m.etapa,
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
        for m in matches
    ]


# =========================================================================
# Frontend HTML
# =========================================================================


@router.get("/matches", response_class=HTMLResponse)
def listar_matches(
    request: Request,
    score_min: Optional[int] = Query(50),
    contacto_id: Optional[int] = Query(None),
    buscar: Optional[str] = Query(None),
    ordenar_por: str = Query("score"),
    orden: str = Query("desc"),
    db: Session = Depends(get_db),
):
    """Página de matches."""
    query = db.query(Match).join(Contacto)

    # Si viene un contacto_id, cargamos el contacto para mostrarlo arriba
    contacto = None
    if contacto_id:
        contacto = db.query(Contacto).filter(Contacto.id == contacto_id).first()
        query = query.filter(Match.contacto_id == contacto_id)
    if score_min is not None:
        query = query.filter(Match.score >= score_min)
    if buscar:
        query = query.join(Propiedad).filter(
            Propiedad.titulo.ilike(f"%{buscar}%")
        )

    # Ordenamiento dinámico
    orden_col = {
        "score": Match.score,
        "fecha": Match.created_at,
        "contacto": Contacto.nombre,
        "propiedad": Propiedad.titulo,
    }
    col = orden_col.get(ordenar_por, Match.score)
    if orden == "asc":
        query = query.order_by(col.asc())
    else:
        query = query.order_by(col.desc())

    matches = query.all()

    contactos = db.query(Contacto).order_by(Contacto.nombre).all()

    # Si es HTMX, devolvemos solo la tabla (pero con filtros para mantener el orden)
    if request.headers.get("HX-Request") == "true":
        templates = request.app.state.jinja_env
        template = templates.get_template("match/_table.html")
        return HTMLResponse(template.render(
            matches=matches,
            contactos=contactos,
            filtros={
                "score_min": score_min or 50,
                "contacto_id": contacto_id or "",
                "buscar": buscar or "",
                "ordenar_por": ordenar_por,
                "orden": orden,
            },
        ))

    template = request.app.state.jinja_env.get_template("match/list.html")
    return HTMLResponse(
        template.render(
            request=request,
            matches=matches,
            contactos=contactos,
            contacto=contacto,
            filtros={
                "score_min": score_min or 50,
                "contacto_id": contacto_id or "",
                "buscar": buscar or "",
                "ordenar_por": ordenar_por,
                "orden": orden,
            },
        )
    )


@router.post("/matches/{match_id}/enviar")
def marcar_enviado(match_id: int, db: Session = Depends(get_db)):
    """Marca un match como 'enviado' (notificado al contacto)."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return JSONResponse(status_code=404, content={"error": "Match no encontrado"})

    match.enviado = True
    db.commit()
    return {"mensaje": "Match marcado como enviado"}
