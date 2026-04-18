from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram
    telegram_bot_token: str
    telegram_user_id: int

    # OpenAI
    openai_api_key: str

    # Google
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8080/callback/google"

    # Microsoft
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"
    microsoft_redirect_uri: str = "http://localhost:8080/callback/microsoft"

    # Security
    token_encryption_key: str

    # Database
    database_path: str = "/data/inboxagent.db"

    # Scheduler
    default_timezone: str = "Europe/London"
    digest_hour: int = 8
    digest_minute: int = 0

    # Digest
    max_emails_per_provider: int = 20
    email_lookback_hours: int = 24

    # OAuth callback
    oauth_callback_host: str = "localhost"
    oauth_callback_port: int = 8080
    oauth_state_timeout_seconds: int = 300


settings = Settings()
