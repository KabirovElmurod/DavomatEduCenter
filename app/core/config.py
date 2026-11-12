from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str
    REDIS_URL: str

    # Bot
    BOT_TOKEN: str
    BOT_USERNAME: str = ""
    BOT_WEBHOOK_SECRET: str = ""

    # Auth
    JWT_SECRET: str
    SESSION_SECRET: str

    # Public URL (for Telegram Login Widget and webhooks)
    PUBLIC_URL: str = "http://localhost:8000"

    # Local dev: Telegram'siz admin login (/admin/dev-login)
    DEV_MODE: bool = False

    # PostgreSQL defaults (for docker-compose)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "education"

    # Webhook settings
    WEBHOOK_HOST: str = ""
    WEBHOOK_PATH: str = "/bot/webhook"


settings = Settings()
