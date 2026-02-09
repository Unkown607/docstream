from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "DocStream"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./docstream.db"

    # Anthropic
    anthropic_api_key: str = ""
    extraction_model: str = "claude-haiku-4-5-20251001"

    # Storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 20

    # Limits
    free_tier_monthly_limit: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
