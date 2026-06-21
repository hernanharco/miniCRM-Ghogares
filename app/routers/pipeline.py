"""
Rutas del Pipeline Comercial.
Vista kanban de matches organizados por etapa del pipeline.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EtapaPipeline, Match

router = APIRouter(tags=["pipeline"])

# Etapas del pipeline en orden
ETAPAS = [
    ("nuevo", "🆕 Nuevo", "border-blue-400 bg-blue-50"),
    ("contactado", "📞 Contactado", "border-yellow-400 bg-yellow-50"),
    ("negociacion", "🤝 En negociación", "border-purple-400 bg-purple-50"),
    ("cerrado", "✅ Cerrado", "border-green-400 bg-green-50"),
    ("perdido", "❌ Perdido", "border-gray-400 bg-gray-50"),
]

# ---------------------------------------------------------------------------
# HTML / Kanban
# ---------------------------------------------------------------------------


@router.get("/pipeline", response_class=HTMLResponse)
def ver_pipeline(request: Request, db: Session = Depends(get_db)):
    """Vista kanban del pipeline comercial."""
    jinja = request.app.state.jinja_env
    matches = (
        db.query(Match)
        .order_by(Match.created_at.desc())
        .all()
    )

    # Agrupar por etapa
    columnas = []
    for key, label, estilo in ETAPAS:
        cards = [m for m in matches if m.etapa == key]
        columnas.append({
            "key": key,
            "label": label,
            "estilo": estilo,
            "cards": cards,
            "count": len(cards),
        })

    return HTMLResponse(
        jinja.get_template("pipeline/index.html").render(
            request=request,
            columnas=columnas,
            total=len(matches),
        )
    )


# ---------------------------------------------------------------------------
# HTMX: mover match entre etapas
# ---------------------------------------------------------------------------


@router.post("/pipeline/{match_id}/mover")
def mover_match(
    match_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Mueve un match a otra etapa del pipeline (HTMX)."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return HTMLResponse("Match no encontrado", status_code=404)

    data = request.query_params
    nueva_etapa = data.get("etapa", "")
    if nueva_etapa not in [e.value for e in EtapaPipeline]:
        return HTMLResponse("Etapa inválida", status_code=400)

    match.etapa = nueva_etapa
    db.commit()

    # Devolver la tarjeta actualizada para que HTMX haga swap
    jinja = request.app.state.jinja_env
    return HTMLResponse(
        jinja.get_template("pipeline/_card.html").render(match=match)
    )


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@router.get("/api/pipeline")
def api_pipeline(db: Session = Depends(get_db)):
    """Lista todos los matches con su etapa."""
    matches = db.query(Match).order_by(Match.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "propiedad_id": m.propiedad_id,
            "contacto_id": m.contacto_id,
            "score": m.score,
            "etapa": m.etapa,
            "enviado": m.enviado,
            "created_at": str(m.created_at),
        }
        for m in matches
    ]


@router.post("/api/pipeline/{match_id}/mover")
def api_mover_match(match_id: int, etapa: str, db: Session = Depends(get_db)):
    """API JSON para mover match de etapa."""
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        return JSONResponse({"error": "Match no encontrado"}, status_code=404)

    if etapa not in [e.value for e in EtapaPipeline]:
        return JSONResponse({"error": "Etapa inválida"}, status_code=400)

    match.etapa = etapa
    db.commit()
    return {"ok": True, "match_id": match_id, "etapa": etapa}
