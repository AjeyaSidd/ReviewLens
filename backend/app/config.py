from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    gemini_api_key: str
    gemini_embedding_api_key: str
    admin_api_key: str
    max_active_apps: int = 15
    max_reviews_per_app: int = 2000
    gemini_sentiment_batch_size: int = 30
    gemini_sentiment_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimensions: int = 1536
    cors_origins: str = "http://localhost:3000"
    log_dir: str = "backend/logs"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache
def get_settings() -> Settings:
    return Settings()
