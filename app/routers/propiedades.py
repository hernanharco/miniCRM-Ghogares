"""
Rutas de propiedades.

Dos caras:
  - /api/propiedades → JSON (para scrapers, GHL, integraciones)
  - /propiedades → HTML (frontend con HTMX)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EstadoPropiedad, Fuente, Propiedad, TipoInmueble
from app.schemas import MensajeResponse, PropiedadCreate, PropiedadResponse

router = APIRouter(tags=["propiedades"])


# =========================================================================
# API JSON
# =========================================================================


@router.get("/api/propiedades", response_model=list[PropiedadResponse])
def listar_propiedades_api(
    zona: Optional[str] = Query(None),
    precio_max: Optional[float] = Query(None),
    precio_min: Optional[float] = Query(None),
    habitaciones: Optional[int] = Query(None),
    tipo: Optional[TipoInmueble] = Query(None),
    estado: Optional[EstadoPropiedad] = Query(None),
    fuente: Optional[Fuente] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista propiedades con filtros opcionales. Devuelve JSON."""
    query = db.query(Propiedad)

    if zona:
        query = query.filter(Propiedad.zona.ilike(f"%{zona}%"))
    if precio_max is not None:
        query = query.filter(Propiedad.precio <= precio_max)
    if precio_min is not None:
        query = query.filter(Propiedad.precio >= precio_min)
    if habitaciones is not None:
        query = query.filter(Propiedad.habitaciones == habitaciones)
    if tipo:
        query = query.filter(Propiedad.tipo == tipo)
    if estado:
        query = query.filter(Propiedad.estado == estado)
    if fuente:
        query = query.filter(Propiedad.fuente == fuente)

    return query.order_by(desc(Propiedad.updated_at)).all()


@router.get("/api/propiedades/{propiedad_id}", response_model=PropiedadResponse)
def obtener_propiedad_api(propiedad_id: int, db: Session = Depends(get_db)):
    """Devuelve una propiedad por ID."""
    prop = db.query(Propiedad).filter(Propiedad.id == propiedad_id).first()
    if not prop:
        return JSONResponse(status_code=404, content={"error": "Propiedad no encontrada"})
    return prop


@router.post("/api/propiedades", response_model=MensajeResponse)
def crear_propiedad_api(data: PropiedadCreate, db: Session = Depends(get_db)):
    """Crea una propiedad manualmente o desde scraper."""
    propiedad = Propiedad(**data.model_dump())
    db.add(propiedad)
    db.commit()
    db.refresh(propiedad)
    return MensajeResponse(id=propiedad.id, mensaje="Propiedad creada")


# =========================================================================
# Frontend HTML (Jinja2 + HTMX)
# =========================================================================


@router.get("/propiedades", response_class=HTMLResponse)
def listar_propiedades(
    request: Request,
    q: Optional[str] = Query(None),
    zona: Optional[str] = Query(None),
    precio_max: Optional[str] = Query(None),
    precio_min: Optional[str] = Query(None),
    habitaciones: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("updated_at"),
    sort_order: Optional[str] = Query("desc"),
    db: Session = Depends(get_db),
):
    """Página de listado de propiedades. Con HTMX para filtros, búsqueda y orden."""
    query = db.query(Propiedad)

    # Búsqueda de texto libre (sobre titulo, direccion, zona)
    if q:
        query = query.filter(
            or_(
                Propiedad.titulo.ilike(f"%{q}%"),
                Propiedad.direccion.ilike(f"%{q}%"),
                Propiedad.zona.ilike(f"%{q}%"),
            )
        )

    if zona:
        query = query.filter(Propiedad.zona.ilike(f"%{zona}%"))
    if precio_max:
        try:
            p_max = float(precio_max)
            query = query.filter(Propiedad.precio <= p_max)
        except (ValueError, TypeError):
            pass
    if precio_min:
        try:
            p_min = float(precio_min)
            query = query.filter(Propiedad.precio >= p_min)
        except (ValueError, TypeError):
            pass
    if habitaciones:
        try:
            query = query.filter(Propiedad.habitaciones == int(habitaciones))
        except (ValueError, TypeError):
            pass
    if tipo:
        try:
            query = query.filter(Propiedad.tipo == TipoInmueble(tipo))
        except (ValueError, TypeError):
            pass
    if estado:
        try:
            query = query.filter(Propiedad.estado == EstadoPropiedad(estado))
        except (ValueError, TypeError):
            pass

    # Ordenamiento
    columnas_validas = {
        "titulo": Propiedad.titulo,
        "precio": Propiedad.precio,
        "zona": Propiedad.zona,
        "habitaciones": Propiedad.habitaciones,
        "metros": Propiedad.metros,
        "estado": Propiedad.estado,
        "fuente": Propiedad.fuente,
        "updated_at": Propiedad.updated_at,
        "created_at": Propiedad.created_at,
    }
    columna = columnas_validas.get(sort_by, Propiedad.updated_at)
    orden = desc if sort_order == "desc" else asc
    propiedades = query.order_by(orden(columna)).all()

    # ── Contadores por tipo y estado ──────────────────────────────────
    # Se calculan sobre la query SIN el filtro del grupo correspondiente
    # para que el usuario vea cuántos hay disponibles en cada opción.

    # Query base para contadores (sin filtro de tipo)
    query_sin_tipo = db.query(Propiedad)
    if q:
        query_sin_tipo = query_sin_tipo.filter(
            or_(
                Propiedad.titulo.ilike(f"%{q}%"),
                Propiedad.direccion.ilike(f"%{q}%"),
                Propiedad.zona.ilike(f"%{q}%"),
            )
        )
    if zona:
        query_sin_tipo = query_sin_tipo.filter(Propiedad.zona.ilike(f"%{zona}%"))
    if precio_max:
        try:
            query_sin_tipo = query_sin_tipo.filter(Propiedad.precio <= float(precio_max))
        except (ValueError, TypeError):
            pass
    if precio_min:
        try:
            query_sin_tipo = query_sin_tipo.filter(Propiedad.precio >= float(precio_min))
        except (ValueError, TypeError):
            pass
    if habitaciones:
        try:
            query_sin_tipo = query_sin_tipo.filter(Propiedad.habitaciones == int(habitaciones))
        except (ValueError, TypeError):
            pass
    # NO aplicar filtro de tipo (para contar)
    if estado:
        try:
            query_sin_tipo = query_sin_tipo.filter(Propiedad.estado == EstadoPropiedad(estado))
        except (ValueError, TypeError):
            pass

    tipo_counts_raw = query_sin_tipo.with_entities(
        Propiedad.tipo, func.count(Propiedad.id)
    ).group_by(Propiedad.tipo).all()
    tipo_counts = {t.value: c for t, c in tipo_counts_raw}
    total_sin_tipo = query_sin_tipo.count()

    # Query base para contadores de estado (sin filtro de estado)
    query_sin_estado = db.query(Propiedad)
    if q:
        query_sin_estado = query_sin_estado.filter(
            or_(
                Propiedad.titulo.ilike(f"%{q}%"),
                Propiedad.direccion.ilike(f"%{q}%"),
                Propiedad.zona.ilike(f"%{q}%"),
            )
        )
    if zona:
        query_sin_estado = query_sin_estado.filter(Propiedad.zona.ilike(f"%{zona}%"))
    if precio_max:
        try:
            query_sin_estado = query_sin_estado.filter(Propiedad.precio <= float(precio_max))
        except (ValueError, TypeError):
            pass
    if precio_min:
        try:
            query_sin_estado = query_sin_estado.filter(Propiedad.precio >= float(precio_min))
        except (ValueError, TypeError):
            pass
    if habitaciones:
        try:
            query_sin_estado = query_sin_estado.filter(Propiedad.habitaciones == int(habitaciones))
        except (ValueError, TypeError):
            pass
    if tipo:
        try:
            query_sin_estado = query_sin_estado.filter(Propiedad.tipo == TipoInmueble(tipo))
        except (ValueError, TypeError):
            pass
    # NO aplicar filtro de estado (para contar)

    estado_counts_raw = query_sin_estado.with_entities(
        Propiedad.estado, func.count(Propiedad.id)
    ).group_by(Propiedad.estado).all()
    estado_counts = {e.value: c for e, c in estado_counts_raw}
    total_sin_estado = query_sin_estado.count()

    # Totales para "Todos" en tipo → sin filtro tipo en la query
    total_sin_tipo = sum(tipo_counts.values())

    # ── Query params actuales ─────────────────────────────────────────
    current_params = {
        "q": q or "",
        "zona": zona or "",
        "precio_max": precio_max or "",
        "precio_min": precio_min or "",
        "habitaciones": habitaciones or "",
        "tipo": tipo or "",
        "estado": estado or "",
        "sort_by": sort_by,
        "sort_order": sort_order,
    }

    # Render común para ambos casos
    render_kwargs = dict(
        propiedades=propiedades,
        tipos=TipoInmueble,
        estados=EstadoPropiedad,
        sort_by=sort_by,
        sort_order=sort_order,
        params=current_params,
        tipo_counts=tipo_counts,
        estado_counts=estado_counts,
        total_sin_tipo=total_sin_tipo,
        total_sin_estado=total_sin_estado,
    )

    # Si es request HTMX, devolvemos la tabla + filtros con OOB swap
    if request.headers.get("HX-Request") == "true":
        templates = request.app.state.jinja_env
        # Tabla como contenido principal
        tabla_html = templates.get_template("propiedades/_table.html").render(**render_kwargs)
        # Filtros con contadores actualizados (OOB swap para que también se actualice el selector)
        filtros_html = templates.get_template("propiedades/_filtros.html").render(
            tipos=TipoInmueble,
            estados=EstadoPropiedad,
            tipo_counts=tipo_counts,
            estado_counts=estado_counts,
            total_sin_tipo=total_sin_tipo,
            total_sin_estado=total_sin_estado,
            filtros=current_params,
        )
        # Envolver filtros con el mismo estilo que list.html + marca OOB
        oob_filtros = f'<div id="filtros-propiedades" hx-swap-oob="true" class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">{filtros_html}</div>'
        return HTMLResponse(tabla_html + oob_filtros)

    # Request normal: página completa
    template = request.app.state.jinja_env.get_template("propiedades/list.html")
    return HTMLResponse(
        template.render(request=request, filtros=current_params, **render_kwargs)
    )


@router.get("/propiedades/{propiedad_id}", response_class=HTMLResponse)
def detalle_propiedad(propiedad_id: int, request: Request, db: Session = Depends(get_db)):
    """Página de detalle de una propiedad."""
    prop = db.query(Propiedad).filter(Propiedad.id == propiedad_id).first()
    if not prop:
        return HTMLResponse("Propiedad no encontrada", status_code=404)

    template = request.app.state.jinja_env.get_template("propiedades/detail.html")
    return HTMLResponse(
        template.render(request=request, prop=prop)
    )


@router.post("/propiedades/{propiedad_id}/estado")
def cambiar_estado(
    propiedad_id: int,
    request: Request,
    estado: EstadoPropiedad = Query(...),
    db: Session = Depends(get_db),
):
    """Cambia el estado de una propiedad (disponible → reservada → vendida)."""
    prop = db.query(Propiedad).filter(Propiedad.id == propiedad_id).first()
    if not prop:
        return JSONResponse(status_code=404, content={"error": "No encontrada"})

    prop.estado = estado
    db.commit()

    # Si es HTMX, devolvemos la tabla actualizada
    if request.headers.get("HX-Request") == "true":
        propiedades = db.query(Propiedad).order_by(desc(Propiedad.updated_at)).all()
        templates = request.app.state.jinja_env
        template = templates.get_template("propiedades/_table.html")
        return HTMLResponse(
            template.render(
                propiedades=propiedades,
                tipos=TipoInmueble,
                estados=EstadoPropiedad,
                sort_by="updated_at",
                sort_order="desc",
            )
        )

    return {"mensaje": f"Estado actualizado a {estado.value}"}
