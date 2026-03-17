"""
config.py

Centralised application settings using pydantic-settings.
All modules must import settings from here — never use os.getenv() directly.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    pg_host: str = "127.0.0.1"
    pg_port: int = 5432
    pg_user: str = "guardian"
    pg_password: str = ""
    pg_db: str = "diabetes_guardian"

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # LLM
    gemini_api_key: str = ""
    llm_model: str = "gemini-1.5-pro"


    # Push notifications
    fcm_server_key: str = ""

    # Twilio (emergency calls)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # Security
    secret_key: str = ""

    # Emotion staleness window
    emotion_staleness_hours: int = 2

    # Pipeline scheduler
    pipeline_schedule_hour: int = 2
    pipeline_schedule_minute: int = 0

    # Demo mode — when True:
    #   triage.py uses payload.recorded_at instead of server NOW()
    #   POST /test/check-data-gap endpoint is enabled
    #   Must be False in any production or staging environment
    demo_mode: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
