import logging
import os
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

logger = logging.getLogger("apik.config")
_config: "Config | None" = None
_config_base_dir: Path = Path.cwd()

# APIK_* environment variables override any value from apik.yml.
_ENV_MAP: dict[str, str] = {
    "APIK_HOST":                      "host",
    "APIK_PORT":                      "port",
    "APIK_WORKERS":                   "workers",
    "APIK_RELOAD":                    "reload",
    "APIK_TOOLS_DIR":                 "tools_dir",
    "APIK_DISABLED_TOOLS":            "disabled_tools",
    "APIK_DATABASE_URL":              "database_url",
    "APIK_DATABASE_GENERATE_SCHEMAS": "database_generate_schemas",
    "APIK_GITHUB_CLIENT_ID":          "github_client_id",
    "APIK_GITHUB_CLIENT_SECRET":      "github_client_secret",
}


class Config(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    tools_dir: Path | None = None
    disabled_tools: list[str] = []
    database_url: str | None = None
    database_generate_schemas: bool = False
    github_client_id: str | None = None
    github_client_secret: str | None = None

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


_SYSTEM_CONFIG = Path("/etc/apik/apik.yml")


def load_config(path: Path | None = None, overrides: dict | None = None) -> "Config":
    global _config, _config_base_dir

    if path is None:
        path = _SYSTEM_CONFIG if _SYSTEM_CONFIG.exists() else Path.cwd() / "apik.yml"

    if path.exists():
        _config_base_dir = path.parent
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        logger.info("config file  : %s", path.resolve())
    else:
        data = {}
        logger.info("config file  : %s  (not found — using defaults)", path.resolve())

    # Log active APIK_* env overrides
    active_env = {k: os.environ[k] for k in _ENV_MAP if k in os.environ}
    if active_env:
        for key, val in active_env.items():
            logger.info("env override : %-24s = %s", key, val)
    else:
        logger.info("env override : (none)")

    data = _apply_env(data)

    # Log CLI overrides
    if overrides:
        active_overrides = {k: v for k, v in overrides.items() if v is not None}
        for key, val in active_overrides.items():
            logger.info("cli override : %-24s = %s", key, val)

    if overrides:
        data.update({k: v for k, v in overrides.items() if v is not None})
    _config = Config(**data)

    # Resolve relative tools_dir against the config file location
    if _config.tools_dir is not None and not _config.tools_dir.is_absolute():
        _config = _config.model_copy(
            update={"tools_dir": (_config_base_dir / _config.tools_dir).resolve()}
        )

    # Fall back to ./tools in the working directory when not configured
    if _config.tools_dir is None:
        _config = _config.model_copy(
            update={"tools_dir": (Path.cwd() / "tools").resolve()}
        )

    # Log final resolved configuration
    logger.info("─" * 48)
    logger.info("host         : %s", _config.host)
    logger.info("port         : %s", _config.port)
    logger.info("workers      : %s", _config.workers)
    logger.info("reload       : %s", _config.reload)
    logger.info("tools_dir    : %s", _config.tools_dir)
    if _config.disabled_tools:
        logger.info("disabled     : %s", ", ".join(_config.disabled_tools))
    else:
        logger.info("disabled     : (none)")
    if _config.database_url:
        # Mask password in logs: postgres://user:PASS@host/db → postgres://user:***@host/db
        import re
        masked = re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", _config.database_url)
        logger.info("database     : %s", masked)
        logger.info("gen_schemas  : %s", _config.database_generate_schemas)
    else:
        logger.info("database     : (not configured)")
    logger.info("─" * 48)

    return _config


def get_config() -> "Config":
    global _config
    if _config is None:
        return load_config()
    return _config
