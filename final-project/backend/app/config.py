from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLINIC_", extra="ignore")

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    generator: str = "grounded"
    vllm_url: str = "http://127.0.0.1:8000/v1"
    vllm_model: str = "t-pro-it-2.1"


settings = Settings()
