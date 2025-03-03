import threading
import tomllib
from pathlib import Path
from typing import Dict, Optional

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
    max_tokens: int = Field(
        4096, description="Maximum number of tokens per request"
    )
    temperature: float = Field(1.0, description="Sampling temperature")


class ScreenshotSettings(BaseModel):
    api_key: Optional[str] = Field(None, description="Screenshot API key")
    base_url: Optional[str] = Field(None, description="Screenshot service URL")


class APISettings(BaseModel):
    host: str = Field("0.0.0.0", description="API host")
    port: int = Field(8000, description="API port")
    debug: bool = Field(False, description="Enable debug mode")


class AgentSettings(BaseModel):
    max_active: int = Field(10, description="Maximum number of active agents")
    timeout: int = Field(300, description="Timeout for agent tasks in seconds")
    default_type: str = Field("toolcall", description="Default agent type")


class SecuritySettings(BaseModel):
    require_auth: bool = Field(False, description="Whether to require authentication")
    allowed_origins: list[str] = Field(
        ["http://localhost:3000"],
        description="Allowed CORS origins"
    )


class LoggingSettings(BaseModel):
    level: str = Field("info", description="Logging level")
    file: Optional[str] = Field("agenthub.log", description="Log file path")


class ToolSettings(BaseModel):
    allowed: list[str] = Field(
        ["terminal", "view", "write_code", "search_file", "create_chat_completion", "browser", "finish"],
        description="List of allowed tools"
    )


class BrowserSettings(BaseModel):
    headless: bool = Field(True, description="Run browser in headless mode")
    timeout: int = Field(30, description="Browser operation timeout in seconds")
    screenshots_dir: str = Field("./screenshots", description="Directory for screenshots")


class AppConfig(BaseModel):
    llm: Dict[str, LLMSettings]
    screenshot: Optional[ScreenshotSettings] = None
    api: Optional[APISettings] = None
    agents: Optional[AgentSettings] = None
    security: Optional[SecuritySettings] = None
    logging: Optional[LoggingSettings] = None
    tools: Optional[ToolSettings] = None
    browser: Optional[BrowserSettings] = None


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
        config_path = root / "config" / "config.toml"
        if config_path.exists():
            return config_path
        example_path = root / "config" / "config.example.toml"
        if example_path.exists():
            return example_path
        raise FileNotFoundError("No configuration file found in config directory")

    def _load_config(self) -> dict:
        config_path = self._get_config_path()
        with config_path.open("rb") as f:
            return tomllib.load(f)

    def _load_initial_config(self):
        raw_config = self._load_config()

        # Process LLM settings
        base_llm = raw_config.get("llm", {})
        llm_overrides = {
            k: v for k, v in raw_config.get("llm", {}).items() if isinstance(v, dict)
        }

        default_settings = {
            "model": base_llm.get("model"),
            "base_url": base_llm.get("base_url"),
            "api_key": base_llm.get("api_key"),
            "max_tokens": base_llm.get("max_tokens", 4096),
            "temperature": base_llm.get("temperature", 1.0),
        }

        config_dict = {
            "llm": {
                "default": default_settings,
                **{
                    name: {**default_settings, **override_config}
                    for name, override_config in llm_overrides.items()
                },
            }
        }

        # Add screenshot config if present
        if screenshot_config := raw_config.get("screenshot"):
            config_dict["screenshot"] = screenshot_config

        # Add API settings if present
        if api_config := raw_config.get("api"):
            config_dict["api"] = api_config

        # Add agent settings if present
        if agents_config := raw_config.get("agents"):
            config_dict["agents"] = agents_config

        # Add security settings if present
        if security_config := raw_config.get("security"):
            config_dict["security"] = security_config

        # Add logging settings if present
        if logging_config := raw_config.get("logging"):
            config_dict["logging"] = logging_config

        # Add tools settings if present
        if tools_config := raw_config.get("tools"):
            config_dict["tools"] = tools_config

        # Add browser settings if present
        if browser_config := raw_config.get("browser"):
            config_dict["browser"] = browser_config

        self._config = AppConfig(**config_dict)

    @property
    def screenshot(self) -> Optional[ScreenshotSettings]:
        return self._config.screenshot

    @property
    def llm(self) -> Dict[str, LLMSettings]:
        return self._config.llm

    @property
    def api(self) -> Optional[APISettings]:
        return self._config.api

    @property
    def agents(self) -> Optional[AgentSettings]:
        return self._config.agents

    @property
    def security(self) -> Optional[SecuritySettings]:
        return self._config.security

    @property
    def logging(self) -> Optional[LoggingSettings]:
        return self._config.logging

    @property
    def tools(self) -> Optional[ToolSettings]:
        return self._config.tools

    @property
    def browser(self) -> Optional[BrowserSettings]:
        return self._config.browser

    def get_tools_config(self) -> list[str]:
        """Get list of allowed tools"""
        if self.tools:
            return self.tools.allowed
        return ["terminal", "view", "write_code", "search_file", "create_chat_completion", "browser", "finish"]

    def get_llm_config(self, name: str = "default") -> LLMSettings:
        """Get LLM configuration by name"""
        if name in self.llm:
            return self.llm[name]
        return self.llm["default"]


# Singleton instance
config = Config()


def load_config() -> Config:
    """Get the global config instance"""
    return config
