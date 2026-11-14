"""
Application configuration

This module exposes a singleton `settings` instance that can be imported
throughout the project (e.g., from config import settings).
"""
from typing import Literal
from urllib.parse import quote_plus

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthenticatorSettings(BaseSettings):
    # Load .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # FastAPI application
    APP_NAME: str = "Authenticator API"
    APP_DESCRIPTION: str = "Manage authentication and product licensing"
    APP_VERSION: str = "1.0"

    # Database
    DB_HOST: SecretStr
    DB_PORT: SecretStr
    DB_NAME: SecretStr
    DB_USER: SecretStr
    DB_PASSWORD: SecretStr

    DB_SIZE: int = 5

    @computed_field
    @property
    def DB_URL(self) -> SecretStr:
        # Quote user/password so characters like @ : / # don't break the URL
        user = quote_plus(self.DB_USER.get_secret_value())
        password = quote_plus(self.DB_PASSWORD.get_secret_value())
        host = self.DB_HOST.get_secret_value()
        port = self.DB_PORT.get_secret_value()
        name = self.DB_NAME.get_secret_value()
        return SecretStr(f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}")

    # Licensing
    LICENSE_PRIVATE_KEY: SecretStr
    LICENSE_TOKEN_FORMAT_VERSION: int = 1

    # Paddle
    PADDLE_API_KEY: SecretStr
    PADDLE_ENVIRONMENT: Literal["sandbox", "production"] = "sandbox"
    PADDLE_ORDER_WEBHOOK_SECRET: SecretStr



settings = AuthenticatorSettings() # type: ignore