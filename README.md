# miniCRM-Ghogares

CRM interno para la gestión de propiedades inmobiliarias y matching con contactos de **GHL (Go High Level)**.

Recibe propiedades desde los scrapers de **Fotocasa** e **Idealista**, las empareja automáticamente con leads según sus preferencias, y gestiona el pipeline de ventas.

---

## ⚡ Inicio rápido

```bash
# 1. Entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env   # Ajustar según entorno

# 4. Arrancar (desarrollo)
./run.sh
# o directamente:
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

La app arranca en **http://localhost:8002**

---

## 🐳 Docker (producción)

```bash
# Build
docker compose build

# Arrancar en background
docker compose up -d

# Ver logs
docker compose logs -f

# Detener
docker compose down
```

Expuesto en el puerto **8002**.

---

## 🗂️ Estructura del proyecto

```
miniCRM/
├── app/
│   ├── main.py                  # FastAPI app + dashboard
│   ├── config.py                # Config centralizada (.env)
│   ├── database.py              # SQLAlchemy engine + session
│   ├── models.py                # Propiedad, Contacto, Match
│   ├── schemas.py               # Pydantic schemas
│   ├── routers/
│   │   ├── propiedades.py       # CRUD propiedades
│   │   ├── contactos.py         # CRUD contactos (desde GHL)
│   │   ├── match.py             # Motor de matching
│   │   └── scraper.py           # Integración con scrapers
│   ├── services/
│   │   ├── importador.py        # Importa datos desde scrapers
│   │   ├── mapping_ghl.py       # Mapeo de campos GHL
│   │   └── matcher.py           # Algoritmo de matching
│   ├── templates/               # Jinja2 templates (HTMX)
│   └── static/                  # CSS/JS
├── tests/
│   ├── conftest.py
│   ├── test_contactos.py
│   ├── test_mapping_ghl.py
│   └── test_matcher.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── run.sh
```

---

## 📋 Modelo de datos

### Propiedad
Propiedades inmobiliarias provenientes de scrapers o carga manual.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id_externo` | string | ID del portal origen |
| `fuente` | enum | fotocasa / idealista / manual |
| `precio` | float | Precio normalizado |
| `zona` | string | Zona/barrio |
| `tipo` | enum | piso / casa / atico / etc. |
| `estado` | enum | disponible / reservada / vendida / descartada |

### Contacto
Leads sincronizados desde GHL que buscan vivienda.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id_ghl` | string | ID en GHL |
| `precio_max` | float | Presupuesto máximo |
| `zona` | string | Zona de interés |
| `habitaciones` | int | Habitaciones deseadas |
| `plazo` | string | urgencia (urgente / 1-3m / 3-6m / sin_prisa) |

### Match
Relación entre un contacto y una propiedad con puntuación.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `score` | int | 0-100 (qué tan compatible es) |
| `enviado` | bool | ¿Ya se notificó al contacto? |

---

## 🔗 Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Dashboard |
| `GET` | `/propiedades/` | Lista de propiedades |
| `GET` | `/contactos/` | Lista de contactos |
| `GET` | `/match/` | Resultados de matching |
| `GET` | `/scraper/` | Estado de scrapers |
| `POST` | `/scraper/importar` | Importar datos desde scrapers |

---

## 🔄 Integración con scrapers

miniCRM se conecta con los scrapers de Fotocasa e Idealista a través del servicio `importador.py`. En el arranque (`lifespan`), importa automáticamente las propiedades nuevas desde la base de datos compartida `bayiva.db`.

### Scrapers relacionados
| Proyecto | Repo |
|----------|------|
| scraper-fotocasa | [github.com/hernanharco/scraper-fotocasa](https://github.com/hernanharco/scraper-fotocasa) |
| scraper-idealista | [github.com/hernanharco/scraper-idealista](https://github.com/hernanharco/scraper-idealista) |

---

## 🧠 Motor de matching

El `matcher.py` implementa un algoritmo que asigna un score a cada par (propiedad, contacto)
basado en:

- **Presupuesto**: precio dentro del rango del contacto (±20%)
- **Ubicación**: coincidencia de zona/municipio
- **Tipo de inmueble**: piso, casa, etc.
- **Habitaciones**: coincide con las deseadas
- **Plazo**: contactos urgentes tienen prioridad

---

## 🧪 Tests

```bash
# Todos los tests
.venv/bin/python -m pytest tests/ -v

# Test específico
.venv/bin/python -m pytest tests/test_matcher.py -v
```

---

## 🌐 Despliegue en servidor (NETCUP)

```bash
# 1. Clonar
git clone https://github.com/hernanharco/miniCRM-Ghogares.git
cd miniCRM-Ghogares

# 2. Configurar
cp .env.example .env
# Editar .env con valores de producción

# 3. Build y arrancar
docker compose up -d
```

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./mini_crm.db` | URL de base de datos |
| `PORT` | `8002` | Puerto del servidor |
| `HOST` | `0.0.0.0` | Host de escucha |

---

## 📦 Stack

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | ≥ 3.12 | Lenguaje |
| FastAPI | ≥ 0.115 | Web framework |
| SQLAlchemy | ≥ 2.0 | ORM |
| SQLite | — | Base de datos |
| Jinja2 | ≥ 3.1 | Templates HTML |
| HTMX | — | Interactividad (CDN) |
| Pydantic | ≥ 2.0 | Validación |
| Docker | — | Contenerización |

---

*Proyecto de **Bayiva — Grupo Hogares** © 2026*
