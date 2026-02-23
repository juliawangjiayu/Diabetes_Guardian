"""
config.py

Centralized configuration management using pydantic-settings.
All modules must import settings from this file.
Direct os.getenv() calls are prohibited elsewhere.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from .env file."""

    # Database
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "guardian"
    mysql_password: str = ""
    mysql_db: str = "diabetes_guardian"

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # LLM (Gemini)
    google_api_key: str = ""
    llm_model: str = "gemini-2.0-pro"

    # MCP Servers
    patient_history_mcp_url: str = "http://127.0.0.1:8001"
    location_context_mcp_url: str = "http://127.0.0.1:8002"

    # Push notifications
    fcm_server_key: str = ""

    # Security
    secret_key: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
