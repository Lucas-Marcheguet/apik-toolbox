import argparse
import logging
import shutil
import subprocess
from pathlib import Path

import uvicorn

from .config import load_config

logger = logging.getLogger("apik.cli")

_INPUT_CSS = Path("core/static/css/input.css")
_OUTPUT_CSS = "core/static/css/tailwind.css"
# Generated when an external APIK_TOOLS_DIR needs an extra @source directive.
_WRAPPER_CSS = Path("core/static/css/.input_external.css")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)-16s  %(message)s",
        datefmt="%H:%M:%S",
    )


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


def _tailwind_input(tools_dir: Path | None) -> Path:
    """Return the CSS input path to pass to the Tailwind CLI.

    If *tools_dir* is inside the project, Tailwind v4 auto-detection picks it
    up and the canonical ``input.css`` is used unchanged.

    If *tools_dir* is an external directory (outside the project root), a tiny
    wrapper CSS is generated that adds an explicit ``@source`` directive before
    importing the real ``input.css``.
    """
    if tools_dir is None:
        return _INPUT_CSS
    project_root = Path.cwd().resolve()
    try:
        tools_dir.resolve().relative_to(project_root)
        return _INPUT_CSS  # internal — auto-detected by Tailwind v4
    except ValueError:
        pass  # external directory
    _WRAPPER_CSS.write_text(
        f'@source "{tools_dir.resolve()}/**/*.html";\n'
        '@import "./input.css";\n'
    )
    return _WRAPPER_CSS


def _tw_cmd(input_css: Path, *, watch: bool = False) -> list[str]:
    """Build a ``npm exec`` command that runs the Tailwind v4 CLI."""
    return [
        "npm", "exec", "--", "tailwindcss",
        "-i", str(input_css),
        "-o", _OUTPUT_CSS,
        *(["--watch"] if watch else ["--minify"]),
    ]


def _rebuild_css(tools_dir: Path | None) -> None:
    """Run a one-shot Tailwind build, printing all compile output to the terminal."""
    css_logger = logging.getLogger("apik.css")
    if not shutil.which("npm"):
        css_logger.warning("npm not found — skipping CSS build")
        return
    input_css = _tailwind_input(tools_dir)
    if input_css == _WRAPPER_CSS:
        css_logger.info("@source ext  : %s/**/*.html", tools_dir)
    css_logger.info("input        : %s", input_css)
    css_logger.info("output       : %s", _OUTPUT_CSS)
    css_logger.info("building CSS ...")
    # No capture_output — Tailwind/DaisyUI compile output goes straight to the terminal.
    result = subprocess.run(_tw_cmd(input_css), check=False)
    if result.returncode == 0:
        css_logger.info("CSS build OK")
    else:
        css_logger.error("CSS build failed (exit %d)", result.returncode)


def dev() -> None:
    """Start the development server with Tailwind CSS watching and auto-reload."""
    _setup_logging()
    p = _base_parser("Start the development server (hot-reload + Tailwind watcher)")
    args = p.parse_args()
    overrides = {k: v for k, v in vars(args).items() if v is not None and k != "config"}

    logger.info("━" * 48)
    logger.info("mode         : development")
    logger.info("uv           : %s", shutil.which("uv") or "not found")
    logger.info("npm          : %s", shutil.which("npm") or "not found")
    logger.info("━" * 48)

    config = load_config(
        path=Path(args.config) if args.config else None,
        overrides=overrides,
    )
    _rebuild_css(config.tools_dir)
    input_css = _tailwind_input(config.tools_dir)
    tailwind = subprocess.Popen(_tw_cmd(input_css, watch=True))
    logger.info("Tailwind watcher started (pid %d)", tailwind.pid)
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
    _setup_logging()
    p = _base_parser("Start the production server")
    p.add_argument("--workers", type=int, help="Number of worker processes")
    p.add_argument(
        "--reload", action=argparse.BooleanOptionalAction, default=None,
        help="Enable or disable auto-reload (--reload / --no-reload)",
    )
    args = p.parse_args()
    overrides = {k: v for k, v in vars(args).items() if v is not None and k != "config"}

    logger.info("━" * 48)
    logger.info("mode         : production")
    logger.info("uv           : %s", shutil.which("uv") or "not found")
    logger.info("npm          : %s", shutil.which("npm") or "not found")
    logger.info("━" * 48)

    config = load_config(
        path=Path(args.config) if args.config else None,
        overrides=overrides,
    )
    config.disabled_tools = ["example"]  # Disable the example tool in production
    _rebuild_css(config.tools_dir)
    uvicorn.run(
        "core.main:app",
        host=config.host,
        port=config.port,
        workers=config.workers,
        reload=config.reload,
    )


