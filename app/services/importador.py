"""
Importa propiedades desde la base de datos del scraper existente
hacia la base del CRM Bayiva.

Esto permite que el CRM arranque con datos reales desde el día 1.
"""

import json
import logging
import re
import sqlite3
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import EstadoPropiedad, Fuente, Propiedad, TipoInmueble

logger = logging.getLogger(__name__)


def importar_desde_scraper(db: Session) -> dict:
    """
    Lee la BD del scraper (bayiva.db) e importa propiedades
    que aún no existan en el CRM (evita duplicados por id_externo + fuente).
    """
    scraper_path = Path(settings.scraper_db_path)
    if not scraper_path.exists():
        logger.warning("BD del scraper no encontrada en %s", scraper_path)
        return {"importadas": 0, "omitidas": 0, "error": "Archivo no encontrado"}

    conn = sqlite3.connect(str(scraper_path))
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.execute(
            """
            SELECT DISTINCT id_externo, fuente, titulo, precio, precio_texto,
                   direccion, zona, municipio, provincia, metros, habitaciones,
                   banos, planta, tipo, url, fotos, descripcion
            FROM propiedades
            ORDER BY id
            """
        )
        filas = cursor.fetchall()
    finally:
        conn.close()

    if not filas:
        return {"importadas": 0, "omitidas": 0, "aviso": "BD del scraper vacía"}

    importadas = 0
    omitidas = 0

    for row in filas:
        id_externo = row["id_externo"]
        fuente = row["fuente"]

        # Saltar si ya existe
        existe = (
            db.query(Propiedad)
            .filter(
                Propiedad.id_externo == id_externo,
                Propiedad.fuente == fuente,
            )
            .first()
        )
        if existe:
            omitidas += 1
            continue

        # Mapear tipo
        tipo_str = row["tipo"] or "otro"
        try:
            tipo = TipoInmueble(tipo_str)
        except ValueError:
            tipo = TipoInmueble.OTRO

        # Mapear fuente
        try:
            fuente_enum = Fuente(fuente)
        except ValueError:
            fuente_enum = Fuente.MANUAL

        fotos_raw = row["fotos"]
        if fotos_raw:
            try:
                fotos = json.loads(fotos_raw)
            except (json.JSONDecodeError, TypeError):
                fotos = []
        else:
            fotos = []

        propiedad = Propiedad(
            id_externo=id_externo,
            fuente=fuente_enum,
            titulo=row["titulo"] or "",
            precio=row["precio"] or 0.0,
            precio_texto=row["precio_texto"] or "",
            direccion=row["direccion"] or "",
            zona=row["zona"] or "",
            municipio=row["municipio"],
            provincia=row["provincia"],
            metros=row["metros"],
            habitaciones=row["habitaciones"],
            banos=row["banos"],
            planta=row["planta"],
            tipo=tipo,
            url=_limpiar_url_fotocasa(row["url"] or ""),
            fotos=json.dumps(fotos),
            descripcion=row["descripcion"],
            estado=EstadoPropiedad.DISPONIBLE,
        )
        db.add(propiedad)
        importadas += 1

    db.commit()
    logger.info("Importación completada: %d importadas, %d omitidas", importadas, omitidas)
    return {"importadas": importadas, "omitidas": omitidas}


def _limpiar_url_fotocasa(url: str) -> str:
    """Saca parametros de galeria de imagenes de URLs de Fotocasa."""
    if not url or "fotocasa" not in url:
        return url
    return (
        re.sub(r"[?&](?:from|multimedia|isGalleryOpen|isZoomGalleryOpen)[^&]*", "", url)
        .replace("?&", "?")
        .rstrip("?&")
    )
