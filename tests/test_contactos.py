"""
Tests para el CRUD de contactos.
"""


def test_crear_contacto(client, db):
    """Crear un contacto con los campos básicos."""
    resp = client.post("/api/contactos", json={
        "id_ghl": "ghl_01",
        "nombre": "Juan Pérez",
        "email": "juan@test.com",
        "telefono": "655000000",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["mensaje"] == "Contacto creado"
    assert data["id"] is not None


def test_crear_contacto_con_intencion(client):
    """Crear un contacto con plazo y motivación."""
    resp = client.post("/api/contactos", json={
        "id_ghl": "ghl_02",
        "nombre": "Ana López",
        "precio_max": 300000,
        "zona": "Centro",
        "plazo": "urgente",
        "motivacion": "primera_vivienda",
    })
    assert resp.status_code == 200
    assert resp.json()["mensaje"] == "Contacto creado"


def test_listar_contactos(client, db):
    """Listar contactos creados."""
    client.post("/api/contactos", json={"id_ghl": "ghl_01", "nombre": "Juan"})
    client.post("/api/contactos", json={"id_ghl": "ghl_02", "nombre": "Ana"})

    resp = client.get("/api/contactos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    nombres = {c["nombre"] for c in data}
    assert "Juan" in nombres
    assert "Ana" in nombres


def test_obtener_contacto(client, db):
    """Obtener un contacto por ID."""
    create = client.post("/api/contactos", json={"id_ghl": "ghl_01", "nombre": "Juan"}).json()
    contacto_id = create["id"]

    resp = client.get(f"/api/contactos/{contacto_id}")
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Juan"
    assert resp.json()["id_ghl"] == "ghl_01"


def test_contacto_no_encontrado(client):
    """404 al buscar un contacto inexistente."""
    resp = client.get("/api/contactos/9999")
    assert resp.status_code == 404


def test_filtro_por_plazo(client, db):
    """Filtrar contactos urgentes."""
    client.post("/api/contactos", json={
        "id_ghl": "ghl_01", "nombre": "Urgente", "plazo": "urgente"
    })
    client.post("/api/contactos", json={
        "id_ghl": "ghl_02", "nombre": "Tranqui", "plazo": "sin_prisa"
    })

    resp = client.get("/contactos?plazo=urgente")
    assert resp.status_code == 200
    assert "Urgente" in resp.text


def test_crear_contacto_con_precio_negativo(client):
    """Validar que precio negativo sea rechazado."""
    resp = client.post("/api/contactos", json={
        "id_ghl": "ghl_error",
        "precio_max": -100,
    })
    assert resp.status_code == 422  # Validation error
