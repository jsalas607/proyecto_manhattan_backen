from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno / archivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Base de datos (async, asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://manhattan:manhattan@db:5432/manhattan"

    # Seguridad / JWT
    JWT_SECRET: str = "cambia-esto-en-produccion"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    # Bootstrap del admin global (se crea al arrancar si no hay usuarios)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"

    # Subida de imágenes
    UPLOADS_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 5

    # CORS (lista separada por comas; "*" para permitir todo en desarrollo)
    CORS_ORIGINS: str = "*"

    # Zona horaria de la operación (offset fijo en horas respecto a UTC).
    # Colombia = -5 (no usa horario de verano). Define qué es "hoy" y los
    # rangos de día para inventario, ventas y estadísticas.
    APP_TZ_OFFSET_HOURS: int = -5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
