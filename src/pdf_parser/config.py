from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PDF_PARSER_",
        env_file=".env",
        extra="ignore",
    )

    endpoint: str = "http://192.168.0.194:8080"
    timeout_seconds: float = Field(default=120.0, gt=0)
    retries: int = Field(default=2, ge=0, le=10)
    concurrency: int = Field(default=1, ge=1, le=16)
    use_layout_detection: bool = True
    layout_threshold: float = Field(default=0.5, ge=0, le=1)
    trust_env: bool = False

    @property
    def inference_url(self) -> str:
        return f"{self.endpoint.rstrip('/')}/layout-parsing"

    @property
    def health_url(self) -> str:
        return f"{self.endpoint.rstrip('/')}/health"
