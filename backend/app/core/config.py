from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "ServiceMind Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True

    database_url: str = ""
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_database: str = "servicemind"

    redis_url: str = ""
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379

    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model_name: str = "deepseek-chat"
    llm_timeout_seconds: float = 60.0
    llm_strip_thinking: bool = True
    embedding_api_base: str = ""
    embedding_api_key: str = ""
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    embedding_timeout_seconds: float = 60.0
    default_request_timeout_seconds: float = Field(default=30.0)

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return SQLAlchemy-ready database URL with DATABASE_URL taking priority."""
        if self.database_url:
            return self.database_url

        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{self.mysql_user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def resolved_redis_url(self) -> str:
        """Return Redis URL, preferring REDIS_URL when supplied."""
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def resolved_llm_api_base(self) -> str:
        """Normalize LLM API base URL for OpenAI-compatible providers."""
        return self.llm_api_base.rstrip("/")

    @property
    def resolved_llm_api_key(self) -> str:
        """Allow Ollama-style local endpoints to work without a real API key."""
        if self.llm_api_key:
            return self.llm_api_key
        if "localhost:11434" in self.resolved_llm_api_base or "127.0.0.1:11434" in self.resolved_llm_api_base:
            return "ollama"
        return ""

    @property
    def resolved_embedding_api_base(self) -> str:
        """Use dedicated embedding API base when provided, otherwise reuse the LLM base."""
        return (self.embedding_api_base or self.llm_api_base).rstrip("/")

    @property
    def resolved_embedding_api_key(self) -> str:
        """Use dedicated embedding API key when provided, otherwise reuse the LLM key."""
        return self.embedding_api_key or self.resolved_llm_api_key


settings = Settings()

# TODO: split settings by environment and add validation for external services.
