import subprocess
from pathlib import Path

import uvicorn

from .config import load_config


def dev(config_path: str | None = None) -> None:
    """Start the development server with Tailwind CSS watching and auto-reload."""
    config = load_config(Path(config_path) if config_path else None)
    tailwind = subprocess.Popen(["npm", "run", "css:watch"])
    try:
        uvicorn.run(
            "core.main:app",
            host=config.host,
            port=config.port,
            workers=1,  # reload mode requires exactly 1 worker
            reload=True,
        )
    finally:
        tailwind.terminate()


def start(config_path: str | None = None) -> None:
    """Start the production server using settings from apik.yml."""
    config = load_config(Path(config_path) if config_path else None)
    config.disabled_tools = ["example"]  # Disable the example tool in production
    uvicorn.run(
        "core.main:app",
        host=config.host,
        port=config.port,
        workers=config.workers,
        reload=config.reload,
    )
