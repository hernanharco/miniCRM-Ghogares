"""
Rutas del Scraper.

Permite ejecutar los scrapers de Fotocasa e Idealista desde el CRM,
importar los resultados automaticamente y ver el estado.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EstadoPropiedad, Fuente, Propiedad, TipoInmueble

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scraper"])


# ─── Models ───────────────────────────────────────────────────────────────

class ScraperEjecutarRequest(BaseModel):
    fuente: str = "fotocasa"  # "fotocasa" | "idealista-uc"
    zona: str = "valencia"
    precio_max: Optional[float] = 200000
    precio_min: Optional[float] = None
    max_paginas: int = 3


class ScraperEjecutarResponse(BaseModel):
    status: str  # "ok" | "error"
    fuente: str
    propiedades_encontradas: int = 0
    propiedades_importadas: int = 0
    mensaje: str = ""
    archivo: str = ""
    duracion_seg: float = 0.0


# ─── Config de scrapers ───────────────────────────────────────────────────

SCRAPER_CONFIG: Dict[str, Dict[str, Any]] = {
    "fotocasa-api": {
        "path": Path(settings.scraper_fotocasa_path),
        "venv": Path(settings.scraper_fotocasa_path) / ".venv" / "bin" / "python",
        "comando": ["-m", "src.scraper_api", "buscar"],
        "output_pattern": "fotocasa_api_{zona}_{timestamp}.json",
    },
    "fotocasa": {
        "path": Path(settings.scraper_fotocasa_path),
        "venv": Path(settings.scraper_fotocasa_path) / ".venv" / "bin" / "python",
        "comando": ["-m", "src.main", "buscar"],
        "output_pattern": "fotocasa_{zona}_{timestamp}.json",
    },
    "idealista-hyper": {
        "path": Path(settings.scraper_idealista_path),
        "shell": "/bin/bash",
        "comando": ["./scrapear.sh", "--fuente", "idealista-hyper"],
        "output_pattern": "idealista_{zona}_{timestamp}.json",
    },
}


# ─── API endpoint: ejecutar scraper ──────────────────────────────────────

@router.post("/api/scraper/ejecutar", response_model=ScraperEjecutarResponse)
def ejecutar_scraper(
    req: ScraperEjecutarRequest,
    db: Session = Depends(get_db),
):
    """Ejecuta un scraper (Fotocasa o Idealista) e importa los resultados al CRM."""
    fuente = req.fuente.lower()
    if fuente not in SCRAPER_CONFIG:
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje=f"Fuente no soportada: {fuente}. Opciones: {list(SCRAPER_CONFIG.keys())}",
        )

    config = SCRAPER_CONFIG[fuente]
    scraper_path = config["path"]

    # Verificar que el scraper existe
    if not scraper_path.exists():
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje=f"Scraper no encontrado en: {scraper_path}",
        )

    # Determinar el ejecutable (python venv o shell bash)
    usar_shell = "shell" in config
    ejecutable = Path(config.get("shell", config.get("venv", "")))
    if not ejecutable.exists():
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje=f"Ejecutable no encontrado: {ejecutable}",
        )

    # Generar output path temporal
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zona_archivo = req.zona.lower().replace(" ", "_")
    output_filename = f"crm_{fuente}_{zona_archivo}_{timestamp}.json"
    output_path = scraper_path / output_filename

    # Armar comando
    # Los scrapers con "shell" se ejecutan con bash, los demas con python
    if usar_shell:
        cmd = ["/bin/bash", *config["comando"]]
    else:
        cmd = [str(ejecutable), *config["comando"]]
    cmd += [
        "--zona", req.zona,
        "--max-paginas", str(req.max_paginas),
        "-o", str(output_path),
    ]
    if req.precio_max is not None:
        cmd.extend(["--precio-max", str(int(req.precio_max))])
    if req.precio_min is not None:
        cmd.extend(["--precio-min", str(int(req.precio_min))])

    # No cache (solo disponible en fotocasa Playwright)
    if fuente == "fotocasa":
        cmd.append("--no-cache")
    # fotocasa-api no necesita --no-cache (siempre trae datos frescos)

    logger.info("Ejecutando scraper: %s", " ".join(str(c) for c in cmd))

    # Ejecutar
    start = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(scraper_path),
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
        )
    except subprocess.TimeoutExpired:
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje="El scraper tardó más de 5 minutos. Probá con menos páginas.",
        )
    except Exception as e:
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje=f"Error ejecutando scraper: {e}",
        )

    duracion = (datetime.now() - start).total_seconds()

    if result.returncode != 0:
        error_msg = result.stderr[:500] if result.stderr else "Error desconocido"
        logger.error("Scraper falló: %s", error_msg)
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje=f"Scraper falló (código {result.returncode}): {error_msg}",
            duracion_seg=duracion,
        )

    # Leer resultados
    if not output_path.exists():
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje="El scraper terminó pero no generó archivo de salida",
            duracion_seg=duracion,
        )

    try:
        with open(output_path) as f:
            data = json.load(f)
    except Exception as e:
        return ScraperEjecutarResponse(
            status="error",
            fuente=fuente,
            mensaje=f"Error leyendo JSON de salida: {e}",
            duracion_seg=duracion,
        )

    propiedades_raw = data.get("propiedades", [])
    total_encontradas = len(propiedades_raw)

    # Importar al CRM
    importadas = _importar_propiedades(db, propiedades_raw, fuente)

    # Contar requests a Hyper Solutions (idealista)
    if "idealista" in fuente:
        _incrementar_contador_hyper()

    logger.info(
        "Scraper %s: %d encontradas, %d importadas en %.1f seg",
        fuente, total_encontradas, importadas, duracion,
    )

    return ScraperEjecutarResponse(
        status="ok",
        fuente=fuente,
        propiedades_encontradas=total_encontradas,
        propiedades_importadas=importadas,
        mensaje=f"Scraper completado. {importadas} propiedades nuevas importadas de {total_encontradas} encontradas.",
        archivo=str(output_path),
        duracion_seg=duracion,
    )


# ─── API endpoint: estado del scraper ────────────────────────────────────

@router.get("/api/scraper/estado")
def estado_scraper(db: Session = Depends(get_db)):
    """Devuelve estadisticas de scraping."""
    total_fotocasa = db.query(Propiedad).filter(Propiedad.fuente == Fuente.FOTOCASA).count()
    total_idealista = db.query(Propiedad).filter(Propiedad.fuente == Fuente.IDEALISTA).count()
    total_manual = db.query(Propiedad).filter(Propiedad.fuente == Fuente.MANUAL).count()
    total = db.query(Propiedad).count()
    ultimas = (
        db.query(Propiedad)
        .order_by(Propiedad.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "total_propiedades": total,
        "por_fuente": {
            "fotocasa": total_fotocasa,
            "idealista": total_idealista,
            "manual": total_manual,
        },
        "ultimas_importadas": [
            {
                "id": p.id,
                "titulo": p.titulo,
                "fuente": p.fuente.value if p.fuente else None,
                "precio": p.precio,
                "zona": p.zona,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in ultimas
        ],
    }


# ─── Frontend: página del scraper ────────────────────────────────────────

@router.get("/scraper", response_class=HTMLResponse)
def pagina_scraper(request: Request, db: Session = Depends(get_db)):
    """Página de gestión de scrapers."""
    stats = _obtener_stats(db)

    template = request.app.state.jinja_env.get_template("scraper/index.html")
    return HTMLResponse(
        template.render(request=request, **stats)
    )


@router.post("/api/scraper/ejecutar/{fuente}", response_class=HTMLResponse)
def ejecutar_scraper_html(
    fuente: str,
    request: Request,
    db: Session = Depends(get_db),
    zona: str = Form("valencia"),
    precio_max: Optional[str] = Form(None),
    precio_min: Optional[str] = Form(None),
    max_paginas: int = Form(3),
):
    """Ejecuta scraper y devuelve HTML parcial (para HTMX).
    
    Incluye actualización OOB de las stats para que los contadores
    y la fecha de última ejecución se actualicen automáticamente.
    """
    # Convertir valores vacios a None (sin filtro de precio)
    p_max = float(precio_max) if precio_max else None
    p_min = float(precio_min) if precio_min else None

    req = ScraperEjecutarRequest(
        fuente=fuente,
        zona=zona,
        precio_max=p_max,
        precio_min=p_min,
        max_paginas=max_paginas,
    )
    resultado = ejecutar_scraper(req, db)

    # Obtener stats actualizadas
    stats = _obtener_stats(db)

    # Renderizar resultado + stats (OOB swap)
    tpl_resultado = request.app.state.jinja_env.get_template("scraper/_resultado.html")
    tpl_stats = request.app.state.jinja_env.get_template("scraper/_stats.html")

    html_resultado = tpl_resultado.render(request=request, r=resultado)
    html_stats = tpl_stats.render(**stats)

    # Combinar: el resultado va al target principal, las stats via OOB
    return HTMLResponse(html_resultado + html_stats)


# ─── Helpers ─────────────────────────────────────────────────────────────

def _obtener_stats(db: Session) -> dict:
    """Obtiene estadisticas de scraping incluyendo ultima ejecucion."""
    from sqlalchemy import func as sa_func

    total_fotocasa = db.query(Propiedad).filter(Propiedad.fuente == Fuente.FOTOCASA).count()
    total_idealista = db.query(Propiedad).filter(Propiedad.fuente == Fuente.IDEALISTA).count()

    # Ultima fecha de ejecucion por fuente
    ultima_fc = (
        db.query(sa_func.max(Propiedad.created_at))
        .filter(Propiedad.fuente == Fuente.FOTOCASA)
        .scalar()
    )
    ultima_id = (
        db.query(sa_func.max(Propiedad.created_at))
        .filter(Propiedad.fuente == Fuente.IDEALISTA)
        .scalar()
    )

    def _formatear_fecha(dt) -> str:
        if not dt:
            return "Nunca"
        return dt.strftime("%d/%m/%Y %H:%M")

    # Contador de requests Hyper API
    contador_requests = _leer_contador_hyper()

    return {
        "total_fotocasa": total_fotocasa,
        "total_idealista": total_idealista,
        "ultima_fotocasa": _formatear_fecha(ultima_fc),
        "ultima_idealista": _formatear_fecha(ultima_id),
        "hyper_requests": contador_requests,
    }

def _importar_propiedades(
    db: Session, propiedades_raw: List[Dict[str, Any]], fuente: str
) -> int:
    """Importa propiedades desde JSON del scraper al CRM.
    
    Devuelve cuantas propiedades NUEVAS se importaron.
    """
    importadas = 0

    try:
        # Normalizar nombre de fuente (sacar sufijos de implementacion)
        fuente_clean = fuente.replace("-uc", "").replace("-hyper", "").replace("-api", "")
        try:
            fuente_enum = Fuente(fuente_clean)
        except ValueError:
            # Fallback: si el nombre no corresponde a un enum, inferir
            if "fotocasa" in fuente_clean:
                fuente_enum = Fuente.FOTOCASA
            elif "idealista" in fuente_clean:
                fuente_enum = Fuente.IDEALISTA
            else:
                fuente_enum = Fuente.MANUAL
    except ValueError:
        fuente_enum = Fuente.MANUAL

    for raw in propiedades_raw:
        id_externo = raw.get("id_externo", "")

        # Verificar si ya existe (para actualizar datos como metros, habitaciones)
        existe = (
            db.query(Propiedad)
            .filter(
                Propiedad.id_externo == id_externo,
                Propiedad.fuente == fuente_enum,
            )
            .first()
        )
        if existe:
            # Actualizar campos que pueden haber cambiado o estar vacios
            actualizado = False
            for campo in ("metros", "habitaciones", "banos", "precio", "titulo", "zona", "tipo"):
                nuevo_val = raw.get(campo)
                if nuevo_val is not None and nuevo_val != "":
                    setattr(existe, campo, nuevo_val)
                    actualizado = True
            if actualizado:
                db.commit()
            continue

        # Limpiar URL (sacar parametros de galeria de Fotocasa)
        url_raw = raw.get("url", "") or ""
        url = re.sub(
            r"[?&](?:from|multimedia|isGalleryOpen|isZoomGalleryOpen)[^&]*",
            "",
            url_raw,
        ).replace("?&", "?").rstrip("?&")

        # Mapear tipo
        tipo_str = raw.get("tipo", "otro")
        try:
            tipo = TipoInmueble(tipo_str)
        except ValueError:
            tipo = TipoInmueble.OTRO

        # Mapear fotos (vienen como lista del scraper, el CRM las guarda como JSON string)
        fotos_list = raw.get("fotos", [])
        fotos_json = json.dumps(fotos_list)

        propiedad = Propiedad(
            id_externo=id_externo,
            fuente=fuente_enum,
            titulo=raw.get("titulo", "") or "",
            precio=raw.get("precio", 0.0) or 0.0,
            precio_texto=raw.get("precio_texto", "") or "",
            direccion=raw.get("direccion", "") or "",
            zona=raw.get("zona", "") or "",
            municipio=raw.get("municipio"),
            provincia=raw.get("provincia"),
            metros=raw.get("metros"),
            metros_utiles=raw.get("metros_utiles"),
            habitaciones=raw.get("habitaciones"),
            banos=raw.get("banos"),
            planta=raw.get("planta"),
            tipo=tipo,
            url=url,
            fotos=fotos_json,
            descripcion=raw.get("descripcion"),
            estado=EstadoPropiedad.DISPONIBLE,
        )
        db.add(propiedad)
        importadas += 1

    db.commit()
    return importadas


# ─── Contador de requests Hyper Solutions ────────────────────────────

import json as _json
from pathlib import Path as _Path

COUNTER_FILE = _Path(__file__).resolve().parent.parent / "hyper_requests.json"


def _incrementar_contador_hyper() -> None:
    """Incrementa el contador de requests a Hyper Solutions."""
    count = 0
    if COUNTER_FILE.exists():
        try:
            data = _json.loads(COUNTER_FILE.read_text())
            count = data.get("count", 0)
        except Exception:
            pass
    count += 1
    COUNTER_FILE.write_text(_json.dumps({"count": count, "actualizado": datetime.now().isoformat()}))


def _leer_contador_hyper() -> int:
    """Lee el contador de requests a Hyper Solutions."""
    if COUNTER_FILE.exists():
        try:
            data = _json.loads(COUNTER_FILE.read_text())
            return data.get("count", 0)
        except Exception:
            pass
    return 0
