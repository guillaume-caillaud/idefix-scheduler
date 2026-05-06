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
    telegram_bot_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "")
    webhook_url: str = os.getenv("WEBHOOK_URL", "")  # ex: https://api.example.com
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "change-me-webhook")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_exp_minutes: int = int(os.getenv("JWT_EXP_MINUTES", "720"))
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password_hash: str = os.getenv("ADMIN_PASSWORD_HASH", "")
    admin_login_max_attempts: int = int(os.getenv("ADMIN_LOGIN_MAX_ATTEMPTS", "5"))
    admin_login_window_seconds: int = int(os.getenv("ADMIN_LOGIN_WINDOW_SECONDS", "300"))
    admin_login_lockout_seconds: int = int(os.getenv("ADMIN_LOGIN_LOCKOUT_SECONDS", "900"))
    telegram_auth_max_age_seconds: int = int(os.getenv("TELEGRAM_AUTH_MAX_AGE_SECONDS", "86400"))
    telegram_auth_challenge_ttl_seconds: int = int(os.getenv("TELEGRAM_AUTH_CHALLENGE_TTL_SECONDS", "300"))  # 5 minutes
    telegram_webhook_self_heal_interval_seconds: int = int(
        os.getenv("TELEGRAM_WEBHOOK_SELF_HEAL_INTERVAL_SECONDS", "60")
    )
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost").split(",")
        if o.strip()
    ]


settings = Settings()
