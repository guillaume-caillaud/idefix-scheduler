import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/team_scheduler",
    )
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    webhook_url: str = os.getenv("WEBHOOK_URL", "")  # ex: https://api.example.com
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "change-me-webhook")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_exp_minutes: int = int(os.getenv("JWT_EXP_MINUTES", "720"))
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin123")
    telegram_auth_max_age_seconds: int = int(os.getenv("TELEGRAM_AUTH_MAX_AGE_SECONDS", "86400"))
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost").split(",")
        if o.strip()
    ]


settings = Settings()
