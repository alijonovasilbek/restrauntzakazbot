from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    alembic_database_url: str | None = Field(default=None, alias="ALEMBIC_DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    admin_group_id: int = Field(alias="ADMIN_GROUP_ID")
    payment_card_number: str = Field(alias="PAYMENT_CARD_NUMBER")
    payment_card_owner: str = Field(alias="PAYMENT_CARD_OWNER")
    broadcast_delay_seconds: float = Field(default=0.08, alias="BROADCAST_DELAY_SECONDS")
    default_delivery_fee: int = Field(default=15000, alias="DEFAULT_DELIVERY_FEE")
    use_redis: bool = Field(default=False, alias="USE_REDIS")
    tz: str = Field(default="Asia/Tashkent", alias="TZ")
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(default=8000, alias="WEB_PORT")
    webapp_base_url: str = Field(default="", alias="WEBAPP_BASE_URL")

    @model_validator(mode="after")
    def normalize_database_urls(self) -> "Settings":
        if not self.alembic_database_url:
            self.alembic_database_url = self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

        app_target = _normalize_database_target(self.database_url)
        alembic_target = _normalize_database_target(self.alembic_database_url)
        if app_target != alembic_target:
            raise ValueError("DATABASE_URL and ALEMBIC_DATABASE_URL must point to the same database")
        return self

    @computed_field
    @property
    def legacy_admin_ids(self) -> set[int]:
        return {int(item.strip()) for item in self.admin_ids_raw.split(",") if item.strip()}


def _normalize_database_target(url: str) -> str:
    parsed = urlsplit(url)
    scheme = parsed.scheme.split("+", 1)[0]
    return urlunsplit((scheme, parsed.netloc, parsed.path, "", ""))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
