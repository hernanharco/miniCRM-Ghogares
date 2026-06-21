"""
Sincroniza contactos desde GHL (API) al miniCRM.
Ejecutar con cron: cada 30 minutos o diario.
"""

import logging
import os
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Contacto
from app.services.matcher import matchear_contacto

logger = logging.getLogger(__name__)

GHL_API_KEY = os.getenv("GHL_API_KEY", "")
GHL_LOCATION_ID = "zXnGSTcBEhT8AR8VnYTc"
GHL_BASE = "https://services.leadconnectorhq.com"
HEADERS = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Version": "2021-07-28",
    "Content-Type": "application/json",
}

# Mapeo de IDs internos de GHL → nombres de campo del modelo Contacto
# La API de GHL devuelve customFields como array de {id, value}
# Estos IDs se obtuvieron de GET /locations/{locationId}/customFields
GHL_FIELD_IDS: dict[str, str] = {
    "lu1fjrSjhipczYK4iaHt": "zona_interes",
    "6GRpumHlkfZb4LHx0Vma": "presupuesto_max",
    "yQoFpe31OipgsrIZaeme": "habitaciones",
    "06UT7mLpHPPRjh0KVkQH": "metros_min",
    "9IR5vD9jT83nzP3oRkHL": "tipo_inmueble",
    "CrerCmxhQQ38tNCMLHct": "plazo",
    "zBai7V5nkRIcy24WAvDS": "motivacion",
}


def fetch_ghl_contacts(limit: int = 100) -> list[dict]:
    """Obtiene contactos desde GHL."""
    if not GHL_API_KEY:
        logger.error("GHL_API_KEY no configurada")
        return []

    url = f"{GHL_BASE}/contacts/?locationId={GHL_LOCATION_ID}&limit={limit}"
    resp = httpx.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("contacts", [])


def sync_contact_to_minicrm(ghl_contact: dict, db: Session) -> Contacto | None:
    """Crea o actualiza un contacto en el miniCRM desde GHL."""
    ghl_id = ghl_contact.get("id")
    email = ghl_contact.get("email") or f"ghl_{ghl_id}"

    # Verificar duplicados
    existente = db.query(Contacto).filter(Contacto.id_ghl == ghl_id).first()
    if existente:
        # Actualizar si le falta nombre o datos básicos
        actualizado = False
        if not existente.nombre:
            existente.nombre = ghl_contact.get("contactName") or ghl_contact.get("name") or existente.nombre
            actualizado = True
        if not existente.email:
            existente.email = ghl_contact.get("email") or existente.email
            actualizado = True
        if not existente.telefono:
            existente.telefono = ghl_contact.get("phone") or existente.telefono
            actualizado = True
        if actualizado:
            db.commit()
            logger.info(f"Contacto {existente.id} actualizado: nombre={existente.nombre}")
        return None

    # Extraer custom fields
    # GHL API devuelve customFields como array de {id, value}
    # Lo convertimos a dict usando el mapeo de IDs → nombres
    custom_fields_array = ghl_contact.get("customFields") or []
    custom: dict[str, str] = {}
    if isinstance(custom_fields_array, list):
        for item in custom_fields_array:
            field_id = item.get("id") if isinstance(item, dict) else None
            field_name = GHL_FIELD_IDS.get(field_id) if field_id else None
            if field_name:
                custom[field_name] = item.get("value")
    elif isinstance(custom_fields_array, dict):
        # Fallback: si GHL cambia el formato a dict
        custom = custom_fields_array

    contacto = Contacto(
        id_ghl=ghl_id,
        nombre=ghl_contact.get("contactName") or ghl_contact.get("name") or "",
        email=email,
        telefono=ghl_contact.get("phone", ""),
        zona=custom.get("zona_interes"),
        precio_max=_to_float(custom.get("presupuesto_max")),
        habitaciones=_to_int(custom.get("habitaciones")),
        metros_min=_to_int(custom.get("metros_min")),
        tipo=custom.get("tipo_inmueble"),
        plazo=custom.get("plazo"),
        motivacion=custom.get("motivacion"),
    )
    db.add(contacto)
    db.commit()
    db.refresh(contacto)

    # Matching automático
    try:
        matches = matchear_contacto(db, contacto.id, score_minimo=50)
        logger.info(f"Contacto {contacto.id}: {len(matches)} matches")
    except Exception as e:
        logger.warning(f"Error en matching para {contacto.id}: {e}")

    return contacto


def run_sync():
    """Ejecuta sincronización completa."""
    logger.info("=== Sincronizando contactos desde GHL ===")
    contacts = fetch_ghl_contacts(limit=100)

    if not contacts:
        logger.info("No hay contactos nuevos")
        return

    db = SessionLocal()
    try:
        creados = 0
        for c in contacts:
            result = sync_contact_to_minicrm(c, db)
            if result:
                creados += 1
        logger.info(f"Sincronización completa: {creados} nuevos contactos")
    finally:
        db.close()


def _to_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _to_int(val):
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_sync()
