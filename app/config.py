"""
Configuración centralizada del CRM Bayiva.
Toma valores de .env con defaults sensatos.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # --- BD del CRM ---
    database_url: str = "sqlite:///./mini_crm.db"

    # --- Directorio base: tareas/ ────────────────────────────────
    _BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    # --- BD del scraper (solo lectura) ---
    scraper_db_path: str = str(_BASE_DIR / "bayiva.db")

    # --- Rutas a los scrapers ---
    scraper_fotocasa_path: str = str(_BASE_DIR / "scraperfotocasa")
    scraper_idealista_path: str = str(_BASE_DIR / "scraperidealista")

    # --- Rutas internas ---
    templates_dir: str = "app/templates"
    static_dir: str = "app/static"

    # --- Puerto / Host ---
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
