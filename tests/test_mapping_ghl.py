"""
Tests para el mapping de campos GHL → CRM.
"""

from app.services.mapping_ghl import transformar_contacto, GHL_FIELD_MAP


def test_transformar_contacto_basico():
    """Transformar payload mínimo de GHL."""
    payload = {
        "id": "ghl_abc123",
        "name": "María García",
        "email": "maria@email.com",
        "phone": "+34612345678",
    }
    result = transformar_contacto(payload)
    assert result["id_ghl"] == "ghl_abc123"
    assert result["nombre"] == "María García"
    assert result["email"] == "maria@email.com"
    assert result["telefono"] == "+34612345678"


def test_transformar_con_campos_personalizados():
    """Transformar payload con custom fields de GHL."""
    payload = {
        "id": "ghl_002",
        "name": "Ana López",
        "custom": {
            "zona_interes": "Centro",
            "presupuesto_max": "250000",
            "habitaciones": "3",
            "metros_min": "80",
            "tipo_inmueble": "piso",
            "plazo": "urgente",
            "motivacion": "primera_vivienda",
        },
    }
    result = transformar_contacto(payload)
    assert result["nombre"] == "Ana López"
    assert result["zona"] == "Centro"
    assert result["precio_max"] == 250000.0
    assert result["habitaciones"] == 3
    assert result["metros_min"] == 80
    assert result["tipo"].value == "piso"
    assert result["plazo"] == "urgente"
    assert result["motivacion"] == "primera_vivienda"


def test_transformar_sin_campos():
    """Payload vacío → solo id_ghl generado."""
    result = transformar_contacto({"email": "test@test.com"})
    assert result["id_ghl"] == "ghl_test@test.com"


def test_mapping_tiene_campos_nuevos():
    """El mapping incluye plazo y motivacion."""
    assert "custom.plazo" in GHL_FIELD_MAP
    assert "custom.motivacion" in GHL_FIELD_MAP
    assert GHL_FIELD_MAP["custom.plazo"] == "plazo"
    assert GHL_FIELD_MAP["custom.motivacion"] == "motivacion"
