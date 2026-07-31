from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PDF_PARSER_",
        env_file=".env",
        extra="ignore",
    )

    endpoint: str = "http://192.168.0.67:8880"
    timeout_seconds: float = Field(default=120.0, gt=0)
    retries: int = Field(default=2, ge=0, le=10)
    concurrency: int = Field(default=1, ge=1, le=16)
    use_layout_detection: bool = True
    layout_threshold: float = Field(default=0.5, ge=0, le=1)
    trust_env: bool = False

    vlm_enabled: bool = False
    vlm_endpoint: str = "http://192.168.0.194:8000"
    vlm_model: str = "qwen3.6-27b"
    vlm_timeout_seconds: float = Field(default=30.0, gt=0)
    vlm_max_attempts: int = Field(default=5, ge=1, le=10)
    vlm_concurrency: int = Field(default=2, ge=1, le=8)
    vlm_seal_ocr_threshold: float = Field(default=0.9, ge=0, le=1)

    @property
    def inference_url(self) -> str:
        return f"{self.endpoint.rstrip('/')}/layout-parsing"

    @property
    def health_url(self) -> str:
        return f"{self.endpoint.rstrip('/')}/health"

    @property
    def vlm_chat_url(self) -> str:
        return f"{self.vlm_endpoint.rstrip('/')}/v1/chat/completions"
