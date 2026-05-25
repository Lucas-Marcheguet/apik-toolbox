import os
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

_config: "Config | None" = None
_config_base_dir: Path = Path.cwd()

# APIK_* environment variables override any value from apik.yml.
_ENV_MAP: dict[str, str] = {
    "APIK_HOST":           "host",
    "APIK_PORT":           "port",
    "APIK_WORKERS":        "workers",
    "APIK_RELOAD":         "reload",
    "APIK_TOOLS_DIR":      "tools_dir",
    "APIK_DISABLED_TOOLS": "disabled_tools",
}


class Config(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    tools_dir: Path | None = None
    disabled_tools: list[str] = []

    @field_validator("tools_dir", mode="before")
    @classmethod
    def parse_tools_dir(cls, v: object) -> Path | None:
        if v is None:
            return None
        return Path(str(v))

    @field_validator("disabled_tools", mode="before")
    @classmethod
    def parse_disabled_tools(cls, v: object) -> list[str]:
        """Accept a YAML list or a comma-separated string (from env vars)."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v) if v else []


def _apply_env(data: dict) -> dict:
    """Overlay APIK_* environment variables on top of file-based config."""
    for env_key, field in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is not None:
            data[field] = val
    return data


def load_config(path: Path | None = None) -> "Config":
    global _config, _config_base_dir

    if path is None:
        path = Path.cwd() / "apik.yml"

    if path.exists():
        _config_base_dir = path.parent
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    data = _apply_env(data)
    _config = Config(**data)

    # Resolve relative tools_dir against the config file location
    if _config.tools_dir is not None and not _config.tools_dir.is_absolute():
        _config = _config.model_copy(
            update={"tools_dir": (_config_base_dir / _config.tools_dir).resolve()}
        )

    return _config


def get_config() -> "Config":
    global _config
    if _config is None:
        return load_config()
    return _config
