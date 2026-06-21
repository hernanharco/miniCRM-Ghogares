# 📱 Scraping de Teléfonos en Idealista y Fotocasa
## Análisis de riesgos legales, técnicos y alternativas para Bayiva

---

## 1. Contexto

Bayiva desarrolla un miniCRM para **Grupo Hogares** (cliente inmobiliario).
El sistema scrapea propiedades de Idealista y Fotocasa para hacer matching con leads de GHL.

Sebastian (fundador de Bayiva) preguntó:
> *"Lo ideal sería que llegue la casa con el número y todo para que se le pueda contactar"*

Este documento analiza si es viable, los riesgos, y las alternativas.

---

## 2. ¿Qué estamos scrapeando hoy? (sin riesgo)

Del **listado público** de Idealista y Fotocasa extraemos:

| Dato | Visible sin login | Riesgo legal |
|---|---|---|
| Título | ✅ Sí | Mínimo |
| Precio | ✅ Sí | Mínimo |
| Dirección / Zona | ✅ Sí | Mínimo |
| Metros, habitaciones, baños | ✅ Sí | Mínimo |
| Tipo de inmueble | ✅ Sí | Mínimo |
| URL de la propiedad | ✅ Sí | Mínimo |
| **Nombre de la agencia** | ✅ Sí (visible en HTML, no lo extraemos aún) | **Mínimo** |

> ✅ Todo esto es información pública, indexable por Google, sin interacción del usuario.

---

## 3. ¿Qué implica scrapear el teléfono? (riesgo alto)

### 3.1. Técnicamente

El teléfono NO está visible en la página. Requiere:

```
1. Navegar a la página de detalle (Playwright)
2. Hacer clic humano en "Ver teléfono" ← interacción
3. Esperar que el JavaScript cargue el número via API
4. Extraerlo del DOM
```

### 3.2. Legalmente

Idealista y Fotocasa **prohíben explícitamente** en sus Términos de Servicio:

> *"Queda prohibido acceder o intentar acceder a cualquier área del Sitio Web o de los Servicios por medios automatizados (incluido el uso de scripts o web crawlers)."*
> — Idealista, Términos y Condiciones

> *"El usuario se obliga a no emplear ningún dispositivo, software o rutina que interfiera en el correcto funcionamiento del sitio web."*
> — Fotocasa, Términos y Condiciones

**No es un delito penal**, pero es un **incumplimiento contractual civil**.

### 3.3. Escenarios de riesgo

| Escenario | Probabilidad | Impacto en Grupo Hogares | Impacto en Bayiva |
|---|---|---|---|
| Bloqueo de IP por tráfico anómalo | Alta | ❌ Pierde scraping de propiedades | ⚠️ Cliente disconforme |
| Bloqueo permanente de Idealista/Fotocasa | Media | ❌❌ Sin acceso a datos de mercado | ⚠️⚠️ Cliente busca otro proveedor |
| Carta de cese y desistimiento | Baja | ⚠️ Exposición legal | 🔴 Bayiva mencionada como desarrollador |
| Demanda por competencia desleal | Muy baja | 🔴🔴🔴 | 🔴🔴🔴 |

### 3.4. El dato clave

El número que se obtiene **NO es del propietario de la vivienda**. Es de la **agencia inmobiliaria** que publicó el anuncio. Llamar a esa agencia para ofrecerle servicios tiene poco sentido comercial porque:
- Ya están vendiendo esa propiedad
- Ya tienen un pipeline activo
- Sería una llamada en frío a un competidor o a un intermediario

---

## 4. Alternativas (ordenadas de mejor a peor)

### 🥇 Opción A (RECOMENDADA): Capturar agencia + lead automático en GHL

**Qué hace:**
- Del listado ya podemos extraer el **nombre de la agencia** (visible, sin clics)
- Al importar una propiedad, el sistema crea un **lead en GHL** con los datos

```
Ejemplo de lead en GHL:
  Nombre:     "Agencia Inmobiliaria X"
  Teléfono:   (vacío)
  Nota:       "Publicó: Piso en Calle Colón, 12 - 1.275.000€
               Zona: El Pla del Remei, Valencia
               URL: https://fotocasa.es/.../189911978/d
               Agencia detectada automáticamente"
  Etiqueta:   "Posible contacto comercial"
```

**Riesgo legal:** ✅ Mínimo (datos públicos)
**Tiempo implementación:** 1-2 días
**Utilidad para Grupo Hogares:** Alta — Sebastian decide a quién contactar

### 🥈 Opción B (mixta): Lo mismo + Grupo Hogares decide si contacta

**Qué hace:**
- Igual que Opción A
- Grupo Hogares recibe los leads y manualmente mira el anuncio
- Si le interesa la agencia, busca el teléfono él mismo (1 clic en "Ver teléfono")

**Riesgo legal:** ✅ Mínimo
**Utilidad:** Alta — el esfuerzo manual lo hace el cliente

### 🥉 Opción C (bajo demanda): Scraping de teléfono con responsabilidad del cliente

**Qué hace:**
- Se implementa la extracción de teléfono vía Playwright
- Bayiva entrega la funcionalidad con una **cláusula contractual**
- Grupo Hogares asume la responsabilidad legal del uso

**Riesgo legal:** ⚠️ Medio-Alto
**Tiempo:** 2-3 semanas
**Requisito:** Cláusula en contrato + documentación de riesgos

---

## 5. Recomendación final para Bayiva

### Sobre el teléfono
1. 📌 Si Grupo Hogares lo exige, entregarlo con:
   - Cláusula contractual donde ellos asumen el riesgo
   - Implementación conservadora (bajo volumen, con controles)
   - Documentación de los TOS que se están violando

