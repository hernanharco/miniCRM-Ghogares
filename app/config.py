"""
Configuración centralizada del CRM Bayiva.
Toma valores de .env con defaults sensatos.

En Docker (Coolify), las rutas a scrapers se ignoran porque
los scrapers corren como contenedores independientes.
En desarrollo local, apuntan a tareas/ automáticamente.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # --- BD del CRM ---
    # En Docker: postgresql://user:pass@supabase:5432/bayiva
    # En local: sqlite:///./data/mini_crm.db (persistente en ./data/)
    database_url: str = "sqlite:///./data/mini_crm.db"

    # --- Supabase (para validar JWT) ─────────────────────────────
    supabase_jwt_secret: str = "565c1bc6029fb4e2d8417c50acb52b8d8e4ef405a1f9044826486222e4bd76e6"
    supabase_url: str = "https://api.bayiva.com"

    # --- CORS ────────────────────────────────────────────────────
    cors_origins: str = "https://portal.bayiva.com,https://minicrm.bayiva.com,http://localhost:8002"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Directorio base (solo para dev local) ───────────────────
    _BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    # --- BD del scraper (solo para importación manual) ───────────
    # En Docker no se usa (los scrapers escriben directo a Supabase)
    # En local apunta a tareas/bayiva.db automáticamente
    scraper_db_path: str = str(_BASE_DIR / "bayiva.db")

    # --- Rutas a scrapers (solo dev local) ───────────────────────
    # En Docker/Coolify los scrapers son contenedores independientes,
    # estas rutas se dejan vacías y se ignoran
    scraper_fotocasa_path: str = ""
    scraper_idealista_path: str = ""

    # --- Rutas internas ---
    templates_dir: str = "app/templates"
    static_dir: str = "app/static"

    # --- Puerto / Host ---
    host: str = "0.0.0.0"
    port: int = 8002

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
