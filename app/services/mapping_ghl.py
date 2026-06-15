"""
Mapping de campos entre GHL (GoHighLevel) y el CRM Bayiva.

Define la traducción de campos: cuando GHL envía un lead vía webhook,
esta configuración dice en qué campo del modelo Contacto se guarda cada dato.

🔧 Cómo modificar:
  Si en GHL agregan un campo nuevo, solo hay que tocar GHL_FIELD_MAP
  y, si necesita conversión, agregar una entrada en CONVERTERS.
"""

from typing import Any, Optional

from app.models import TipoInmueble

# =============================================================================
# MAPPING: GHL → CRM
# =============================================================================
# Cada entrada es: "campo_en_ghl": "campo_en_modelo_contacto"
#
# 📝 Para campos personalizados de GHL se usa el prefijo "custom."
#    Ej: si en GHL el campo se llama "presupuesto_max", acá va "custom.presupuesto_max"
#
# 📝 Si el campo de GHL es igual al del modelo, se puede omitir.
# =============================================================================

GHL_FIELD_MAP: dict[str, str] = {
    # --- Campos estándar de GHL ---
    "name": "nombre",
    "email": "email",
    "phone": "telefono",
    # "address": no lo usamos (la dirección del lead no es la de la propiedad)
    # "city": no lo usamos (usamos zona, no ciudad del lead)

    # --- Campos personalizados de GHL (custom fields) ---
    # Estos los define Sebastian en GHL; si el nombre cambia, se actualiza acá
    "custom.zona_interes": "zona",
    "custom.presupuesto_max": "precio_max",
    "custom.habitaciones": "habitaciones",
    "custom.metros_min": "metros_min",
    "custom.tipo_inmueble": "tipo",
    "custom.plazo": "plazo",
    "custom.motivacion": "motivacion",
}

# =============================================================================
# CONVERSORES DE TIPO
# =============================================================================
# Algunos campos de GHL vienen como texto y necesitan convertirse al tipo
# que espera el modelo (enums, floats, enteros).
# =============================================================================

# Valores que GHL puede enviar para tipo de inmueble → nuestro enum
TIPO_MAP = {
    "piso": TipoInmueble.PISO,
    "casa": TipoInmueble.CASA,
    "ático": TipoInmueble.ATICO,
    "atico": TipoInmueble.ATICO,
    "dúplex": TipoInmueble.DUPLEX,
    "duplex": TipoInmueble.DUPLEX,
    "local": TipoInmueble.LOCAL,
    "oficina": TipoInmueble.OFICINA,
    "nave": TipoInmueble.NAVE,
    "garaje": TipoInmueble.GARAJE,
    "trastero": TipoInmueble.TRASTERO,
    "otro": TipoInmueble.OTRO,
}

# Conversores por campo destino del modelo
# Cada entrada: "campo_destino": función(valor_ghl) → valor_crm
CONVERTERS: dict[str, callable] = {
    "tipo": lambda v: TIPO_MAP.get(v.lower().strip()) if v else None,
    "precio_max": float,
    "habitaciones": int,
    "metros_min": int,
}


# =============================================================================
# FUNCIONES DE TRANSFORMACIÓN
# =============================================================================


def transformar_contacto(payload: dict) -> dict:
    """
    Toma el payload que llega de GHL (dict) y devuelve un dict
    listo para crear/actualizar un Contacto en el CRM.

    Ejemplo de uso:
        data = transformar_contacto(payload_ghl)
        contacto = Contacto(**data)
    """
    resultado: dict[str, Any] = {}

    # ID de GHL: puede venir en varios formatos según el webhook
    resultado["id_ghl"] = (
        payload.get("id")
        or payload.get("contactId")
        or f"ghl_{payload.get('email', 'unknown')}"
    )

    for campo_ghl, campo_modelo in GHL_FIELD_MAP.items():
        valor = _extraer_valor(payload, campo_ghl)
        if valor is None or valor == "":
            continue

        # Aplicar conversión de tipo si existe
        conversor = CONVERTERS.get(campo_modelo)
        if conversor:
            try:
                valor = conversor(valor)
            except (ValueError, TypeError):
                continue  # Si no se puede convertir, no lo mandamos

        resultado[campo_modelo] = valor

    return resultado


def _extraer_valor(payload: dict, campo_ghl: str) -> Any:
    """
    Extrae un valor del payload de GHL.
    Soporta notación anidada con puntos:
      "name"              → payload["name"]
      "custom.presupuesto" → payload.get("custom", {})["presupuesto"]
    """
    partes = campo_ghl.split(".")
    valor = payload
    for parte in partes:
        if not isinstance(valor, dict):
            return None
        valor = valor.get(parte)
        if valor is None:
            return None
    return valor


def mapear_contacto_a_ghl(contacto) -> dict:
    """
    Transformación inversa: CRM → GHL.
    Útil si algún día queremos actualizar GHL desde el CRM.

    Por ahora no se usa, pero lo dejamos para referencia.
    """
    inverso = {v: k for k, v in GHL_FIELD_MAP.items()}
    resultado = {}
    for campo_modelo, valor in [
        ("nombre", contacto.nombre),
        ("email", contacto.email),
        ("telefono", contacto.telefono),
        ("zona", contacto.zona),
        ("precio_max", contacto.precio_max),
        ("habitaciones", contacto.habitaciones),
        ("metros_min", contacto.metros_min),
        ("plazo", contacto.plazo),
        ("motivacion", contacto.motivacion),
    ]:
        campo_ghl = inverso.get(campo_modelo)
        if campo_ghl and valor is not None:
            resultado[campo_ghl] = valor

    # Tipo: enum → string
    if contacto.tipo:
        ghl_key = inverso.get("tipo")
        if ghl_key:
            resultado[ghl_key] = contacto.tipo.value

    return resultado
