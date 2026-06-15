"""
Algoritmo de matching entre contactos y propiedades.

Devuelve un score 0-100 basado en qué tanto una propiedad
coincide con las preferencias del contacto.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Contacto, Match, Propiedad


def calcular_score(contacto: Contacto, propiedad: Propiedad) -> int:
    """
    Calcula qué tanto matchea una propiedad con un contacto.

    Sistema de puntuación (se normaliza a 100 pts):
      - Precio:        hasta 30 pts
      - Zona:          hasta 30 pts
      - Habitaciones:  hasta 20 pts
      - Metros²:       hasta 20 pts
      - Plazo:         hasta 10 pts (urgencia de la necesidad)
      - Motivación:    hasta 10 pts (alineación con el propósito)
    """
    score = 0
    total_weight = 0

    # --- Precio (30 pts) ---
    if contacto.precio_max and contacto.precio_max > 0:
        total_weight += 30
        if propiedad.precio and propiedad.precio > 0 and propiedad.precio <= contacto.precio_max:
            score += 30
        elif propiedad.precio:
            # Puntuación parcial: qué tan cerca está
            ratio = contacto.precio_max / propiedad.precio
            score += int(30 * min(ratio, 1.0))

    # --- Zona (30 pts) ---
    if contacto.zona:
        total_weight += 30
        if propiedad.zona and propiedad.zona.lower() == contacto.zona.lower():
            score += 30
        elif propiedad.municipio and propiedad.municipio.lower() == contacto.zona.lower():
            score += 20  # Match por municipio (penaliza vs zona exacta)
        elif propiedad.zona and contacto.zona.lower() in propiedad.zona.lower():
            score += 15  # Match parcial

    # --- Habitaciones (20 pts) ---
    if contacto.habitaciones is not None and contacto.habitaciones > 0:
        total_weight += 20
        if propiedad.habitaciones is not None:
            if propiedad.habitaciones == contacto.habitaciones:
                score += 20
            elif propiedad.habitaciones >= contacto.habitaciones:
                # Más habitaciones de las pedidas: aceptable pero penaliza
                score += 15
            elif propiedad.habitaciones >= contacto.habitaciones - 1:
                score += 10  # Una menos: aceptable

    # --- Metros² (20 pts) ---
    if contacto.metros_min is not None and contacto.metros_min > 0:
        total_weight += 20
        if propiedad.metros is not None:
            if propiedad.metros >= contacto.metros_min:
                score += 20
            elif propiedad.metros >= contacto.metros_min * 0.8:
                score += 10  # Al menos 80% del mínimo

    # --- Plazo (10 pts): urgencia de la necesidad ---
    if contacto.plazo:
        total_weight += 10
        if contacto.plazo == "urgente" and propiedad.estado == "disponible":
            score += 10  # Lo necesita ya y está disponible
        elif contacto.plazo == "1-3 meses":
            score += 7
        elif contacto.plazo == "3-6 meses":
            score += 5
        else:
            score += 3  # 6-12 meses, sin_prisa: poco urgente

    # --- Motivación (10 pts): alineación con el propósito ---
    if contacto.motivacion:
        total_weight += 10
        if contacto.motivacion == "primera_vivienda":
            # Primera vivienda: priorizar piso/casa que sean habitables ya
            score += 10 if propiedad.tipo in ("piso", "casa") else 6
        elif contacto.motivacion == "inversion":
            # Inversión: cualquier propiedad puede ser inversión, puntuación base
            score += 8
        elif contacto.motivacion == "ampliacion":
            # Ampliación: prefieren propiedades más grandes
            if propiedad.habitaciones and propiedad.habitaciones >= 3:
                score += 10
            else:
                score += 6
        elif contacto.motivacion == "reduccion":
            # Reducción: prefieren propiedades más pequeñas
            if propiedad.habitaciones and propiedad.habitaciones <= 2:
                score += 10
            else:
                score += 6
        else:
            score += 5  # cambio_zona, segunda_residencia, etc.

    # Normalizar por si hay pocos criterios
    if total_weight == 0:
        return 0

    return int((score / total_weight) * 100)


def matchear_contacto(
    db: Session, contacto_id: int, score_minimo: int = 50
) -> list[dict]:
    """
    Busca propiedades disponibles que matcheen con un contacto.
    Guarda los matches en BD y devuelve los resultados ordenados por score.
    """
    contacto = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not contacto:
        return []

    propiedades = (
        db.query(Propiedad)
        .filter(Propiedad.estado == "disponible")
        .all()
    )

    resultados = []
    for prop in propiedades:
        score = calcular_score(contacto, prop)
        if score >= score_minimo:
            # Verificar si ya existe el match
            existente = (
                db.query(Match)
                .filter(
                    Match.propiedad_id == prop.id,
                    Match.contacto_id == contacto.id,
                )
                .first()
            )
            if not existente:
                match = Match(
                    propiedad_id=prop.id,
                    contacto_id=contacto.id,
                    score=score,
                )
                db.add(match)
                db.commit()
                db.refresh(match)
            else:
                # Actualizar score si cambió
                existente.score = score
                db.commit()
                match = existente

            resultados.append(
                {
                    "match_id": match.id,
                    "score": score,
                    "propiedad": {
                        "id": prop.id,
                        "titulo": prop.titulo,
                        "precio": prop.precio,
                        "zona": prop.zona,
                        "metros": prop.metros,
                        "habitaciones": prop.habitaciones,
                        "url": prop.url,
                    },
                    "contacto": {
                        "id": contacto.id,
                        "nombre": contacto.nombre,
                    },
                }
            )

    # Ordenar por score descendente
    resultados.sort(key=lambda r: r["score"], reverse=True)
    return resultados


def matchear_todos(db: Session, score_minimo: int = 50) -> list[dict]:
    """
    Corre matching para TODOS los contactos activos.
    Útil para procesamiento batch (ej. diario).
    """
    contactos = db.query(Contacto).all()
    todos = []
    for c in contactos:
        matches = matchear_contacto(db, c.id, score_minimo)
        todos.extend(matches)
    return todos
