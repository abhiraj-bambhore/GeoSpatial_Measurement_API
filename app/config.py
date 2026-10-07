from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Supabase credentials are optional — when absent the database layer
    automatically falls back to a local SQLite store so CI and local dev
    work without any cloud credentials.
    """

    supabase_url: str = ""
    supabase_key: str = ""
    upload_dir: str = "uploads"
    max_file_size_mb: int = 50

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
