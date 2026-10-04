from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DRAGONFORGE_", extra="ignore")

    database_url: str = "postgresql+psycopg://dragonforge:dragonforge@localhost:5432/dragonforge"
    session_secret: str | None = None
    totp_encryption_key: str | None = None
    bootstrap_token: str | None = None
    session_cookie_secure: bool = True
    session_ttl_hours: int = 12
    domain: str = "dragonforge.com"
    allowed_origins: list[str] = []


settings = Settings()