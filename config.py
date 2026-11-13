"""
Application configuration

This module exposes a singleton `settings` instance that can be imported
throughout the project (e.g., from config import settings).
"""
from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
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

    LICENSE_PRIVATE_KEY: SecretStr = Field(..., alias="license_private_key")



settings = MLSettings() # type: ignore