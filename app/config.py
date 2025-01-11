import threading
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_project_root()
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"


class LLMSettings(BaseModel):
    model: str = Field(..., description="Model name")
    base_url: str = Field(..., description="API base URL")
    api_key: str = Field(..., description="API key")
    max_tokens: int = Field(4096, description="Maximum number of tokens per request")
    temperature: float = Field(1.0, description="Sampling temperature")


class AppConfig(BaseModel):
    llm: LLMSettings


class Config:
    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._config = None
                    self._load_initial_config()
                    self._initialized = True

    @staticmethod
    def _get_config_path() -> Path:
        root = PROJECT_ROOT
        config_path = root / "config" / "config.yaml"
        if not config_path.exists():
            config_path = root / "config" / "config.example.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                "Configuration file config.yaml or config.example.yaml not found"
            )
        return config_path

    def _load_config(self) -> dict:
        config_path = self._get_config_path()
        with config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _load_initial_config(self):
        raw_config = self._load_config()

        config_dict = {
            "llm": {
                "model": raw_config.get("llm", {}).get("model"),
                "base_url": raw_config.get("llm", {}).get("base_url"),
                "api_key": raw_config.get("llm", {}).get("api_key"),
                "max_tokens": raw_config.get("llm", {}).get("max_tokens", 4096),
                "temperature": raw_config.get("llm", {}).get("temperature", 1.0),
            },
        }

        self._config = AppConfig(**config_dict)

    @property
    def llm(self) -> LLMSettings:
        return self._config.llm


config = Config()
