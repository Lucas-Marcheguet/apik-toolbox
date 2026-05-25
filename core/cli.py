import argparse
import subprocess
from pathlib import Path

import uvicorn

from .config import load_config


def _base_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument(
        "--config", metavar="PATH",
        help="Path to apik.yml (default: /etc/apik/apik.yml, then ./apik.yml)",
    )
    p.add_argument("--host", help="Bind host")
    p.add_argument("--port", type=int, help="Bind port")
    p.add_argument(
        "--tools-dir", dest="tools_dir", metavar="DIR",
        help="Path to the tools directory",
    )
    p.add_argument(
        "--disabled-tools", dest="disabled_tools", metavar="SLUGS",
        help="Comma-separated tool slugs to disable at startup",
    )
    return p


def dev() -> None:
    """Start the development server with Tailwind CSS watching and auto-reload."""
    p = _base_parser("Start the development server (hot-reload + Tailwind watcher)")
    args = p.parse_args()
    overrides = {k: v for k, v in vars(args).items() if v is not None and k != "config"}
    config = load_config(
        path=Path(args.config) if args.config else None,
        overrides=overrides,
    )
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


def start() -> None:
    """Start the production server using settings from apik.yml."""
    p = _base_parser("Start the production server")
    p.add_argument("--workers", type=int, help="Number of worker processes")
    p.add_argument(
        "--reload", action=argparse.BooleanOptionalAction, default=None,
        help="Enable or disable auto-reload (--reload / --no-reload)",
    )
    args = p.parse_args()
    overrides = {k: v for k, v in vars(args).items() if v is not None and k != "config"}
    config = load_config(
        path=Path(args.config) if args.config else None,
        overrides=overrides,
    )
    config.disabled_tools = ["example"]  # Disable the example tool in production
    uvicorn.run(
        "core.main:app",
        host=config.host,
        port=config.port,
        workers=config.workers,
        reload=config.reload,
    )
