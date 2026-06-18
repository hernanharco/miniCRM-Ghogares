"""
Rutas de contactos (desde GHL).
Recibe leads vía webhook desde GHL y los matchea automáticamente.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Contacto, Match, TipoInmueble
from app.schemas import ContactoCreate, ContactoResponse, MensajeResponse
from app.services.matcher import matchear_contacto

router = APIRouter(tags=["contactos"])


# ── Dependencia para webhook de GHL ───────────────────────────
# Acepta tanto JWT (desde el portal) como API key (desde webhook)
def _webhook_o_jwt(
    request: Request,
    x_webhook_key: Optional[str] = Header(None),
):
    """Permite acceso via JWT (portal) o via API key (webhook GHL)."""
    # Si ya pasó el middleware JWT, tiene user en state
    if hasattr(request.state, "user") and request.state.user:
        return True
    # Si viene con la API key del webhook, también pasa
    if x_webhook_key and x_webhook_key == settings.ghl_webhook_key:
        return True
    raise HTTPException(status_code=401, detail="Acceso no autorizado")


# =========================================================================
# API JSON
# =========================================================================


@router.get("/api/contactos", response_model=list[ContactoResponse])
def listar_contactos_api(
    nombre: Optional[str] = Query(None),
    zona: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista contactos."""
    query = db.query(Contacto)

    if nombre:
        query = query.filter(Contacto.nombre.ilike(f"%{nombre}%"))
    if zona:
        query = query.filter(Contacto.zona.ilike(f"%{zona}%"))

    return query.order_by(desc(Contacto.updated_at)).all()


import logging
logger = logging.getLogger(__name__)


@router.post("/api/contactos", response_model=MensajeResponse)
def crear_contacto_api(
    data: ContactoCreate,
    request: Request,
    db: Session = Depends(get_db),
    _auth=Depends(_webhook_o_jwt),
):
    """Crea un contacto manualmente o desde webhook de GHL."""
    import sys
    logger.info("=== WEBHOOK GHL RECIBIDO ===")
    logger.info("Payload: %s", data.model_dump())
    sys.stdout.flush()

    contacto = Contacto(
        id_ghl=data.id_ghl or f"ghl_{data.email or ''}",
        nombre=data.nombre,
        email=data.email,
        telefono=data.telefono,
        precio_max=data.precio_max,
        zona=data.zona,
        habitaciones=data.habitaciones,
        metros_min=data.metros_min,
        tipo=data.tipo,
        notas=data.notas,
        plazo=data.plazo,
        motivacion=data.motivacion,
        propiedad_interes_id=data.propiedad_interes_id,
    )
    db.add(contacto)
    db.commit()
    db.refresh(contacto)

    # Matching automático para este contacto
    try:
        nuevos_matches = matchear_contacto(db, contacto.id, score_minimo=50)
        return MensajeResponse(
            id=contacto.id,
            mensaje=f"Contacto creado con {len(nuevos_matches)} matches"
        )
    except Exception:
        return MensajeResponse(id=contacto.id, mensaje="Contacto creado (matching pendiente)")


@router.get("/api/contactos/{contacto_id}", response_model=ContactoResponse)
def obtener_contacto_api(contacto_id: int, db: Session = Depends(get_db)):
    """Devuelve un contacto por ID."""
    c = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not c:
        return JSONResponse(status_code=404, content={"error": "Contacto no encontrado"})
    return c


# =========================================================================
# Frontend HTML
# =========================================================================


@router.get("/contactos", response_class=HTMLResponse)
def listar_contactos(
    request: Request,
    nombre: Optional[str] = Query(None),
    plazo: Optional[str] = Query(None),
    motivacion: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Página de listado de contactos."""
    query = db.query(Contacto)
    if nombre:
        query = query.filter(Contacto.nombre.ilike(f"%{nombre}%"))
    if plazo:
        query = query.filter(Contacto.plazo == plazo)
    if motivacion:
        query = query.filter(Contacto.motivacion == motivacion)
    contactos = query.order_by(desc(Contacto.updated_at)).all()

    if request.headers.get("HX-Request") == "true":
        templates = request.app.state.jinja_env
        template = templates.get_template("contactos/_table.html")
        return HTMLResponse(template.render(contactos=contactos))

    template = request.app.state.jinja_env.get_template("contactos/list.html")
    return HTMLResponse(
        template.render(
            request=request,
            contactos=contactos,
            filtros={
                "nombre": nombre or "",
                "plazo": plazo or "",
                "motivacion": motivacion or "",
            },
        )
    )


@router.get("/contactos/{contacto_id}", response_class=HTMLResponse)
def detalle_contacto(
    request: Request,
    contacto_id: int,
    db: Session = Depends(get_db),
):
    """Página de detalle de un contacto con sus matches."""
    c = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not c:
        return HTMLResponse("Contacto no encontrado", status_code=404)

    # Matches existentes
    matches = (
        db.query(Match)
        .filter(Match.contacto_id == contacto_id)
        .order_by(desc(Match.score))
        .all()
    )

    template = request.app.state.jinja_env.get_template("contactos/detail.html")
    return HTMLResponse(
        template.render(request=request, c=c, matches=matches)
    )


@router.post("/api/contactos/{contacto_id}/matchear")
def matchear_contacto_endpoint(
    contacto_id: int,
    db: Session = Depends(get_db),
):
    """
    Ejecuta matching para un contacto y devuelve HTML parcial
    con la tabla de resultados (para HTMX).
    """
    resultados = matchear_contacto(db, contacto_id)

    if not resultados:
        return HTMLResponse(
            '<p class="text-sm text-gray-500 text-center py-8">'
            "No se encontraron matches con el score mínimo.</p>"
        )

    rows = ""
    for r in resultados:
        score = r["score"]
        prop = r["propiedad"]
        color = "bg-green-500" if score >= 80 else "bg-yellow-500" if score >= 60 else "bg-gray-400"
        text_color = "text-green-700" if score >= 80 else "text-yellow-700" if score >= 60 else "text-gray-500"

        rows += f"""<tr class="hover:bg-gray-50 transition-colors">
            <td class="px-3 py-2">
                <a href="/propiedades/{prop['id']}" class="text-sm text-brand-600 hover:underline">
                    {prop['titulo'] or 'Propiedad #' + str(prop['id'])}
                </a>
            </td>
            <td class="px-3 py-2 text-sm text-right text-gray-900">
                {f"{{:,.0f}}".format(prop['precio']) + ' €' if prop['precio'] else '-'}
            </td>
            <td class="px-3 py-2 text-center">
                <span class="inline-flex items-center gap-1 text-xs font-medium {text_color}">
                    <span class="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden inline-block">
                        <span class="block h-full rounded-full {color}" style="width: {score}%"></span>
                    </span>
                    {score}%
                </span>
            </td>
            <td class="px-3 py-2 text-center">
                <span class="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Nuevo</span>
            </td>
            <td class="px-3 py-2 text-right">
                <a href="/propiedades/{prop['id']}"
                   class="text-xs px-2 py-1 bg-brand-50 text-brand-600 rounded hover:bg-brand-100 transition-colors">
                    Ver propiedad
                </a>
            </td>
        </tr>"""

    return HTMLResponse(
        f"""<div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="text-left text-xs font-medium text-gray-500 uppercase px-3 py-2">Propiedad</th>
                        <th class="text-right text-xs font-medium text-gray-500 uppercase px-3 py-2">Precio</th>
                        <th class="text-center text-xs font-medium text-gray-500 uppercase px-3 py-2">Score</th>
                        <th class="text-center text-xs font-medium text-gray-500 uppercase px-3 py-2">Estado</th>
                        <th class="text-right text-xs font-medium text-gray-500 uppercase px-3 py-2">Acción</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {rows}
                </tbody>
            </table>
        </div>"""
    )
