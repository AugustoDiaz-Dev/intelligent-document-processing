from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"

    database_url: str

    # OCR provider: mock | paddleocr | aws_textract
    ocr_provider: str = "mock"
    paddle_lang: str = "en"
    paddle_use_gpu: bool = False

    # AWS Textract (only needed when ocr_provider=aws_textract)
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Extraction mode: simple (regex) | llm (OpenAI)
    extraction_mode: str = "simple"
    openai_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"


settings = Settings()

