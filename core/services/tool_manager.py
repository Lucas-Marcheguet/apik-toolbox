"""
Tool discovery and registration.

A valid tool directory must contain:
  - manifest.yml   — metadata (name, slug, description, version)
  - __init__.py    — must expose a `router: APIRouter` attribute
  - index.html     — entry-point template (served at GET /tools/{slug}/)

The tool's Jinja2 `templates` object (if present on the module) is patched so
that it can also resolve the main app's templates (e.g. ``base.html``).

Tools can freely define sub-routers inside their own `router` and organise
additional templates / static files as they see fit.
"""

import importlib.util
import logging
import shutil
import subprocess
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

logger = logging.getLogger("apik.tools")

PACKAGE_DIR = Path(__file__).parent.parent
MAIN_TEMPLATES_DIR = PACKAGE_DIR / "templates"

# Namespace package used so tools can use relative imports among their own
# sub-modules (e.g. ``from . import utils``).
_NAMESPACE = "apik_tools"


@dataclass
class ToolManifest:
    name: str
    slug: str
    description: str
    version: str
    dependencies: list[str] = field(default_factory=list)


@dataclass
class LoadedTool:
    manifest: ToolManifest
    router: APIRouter
    tool_dir: Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_namespace() -> None:
    """Register the ``apik_tools`` parent package once."""
    if _NAMESPACE not in sys.modules:
        pkg = types.ModuleType(_NAMESPACE)
        pkg.__path__ = []  # type: ignore[attr-defined]
        pkg.__package__ = _NAMESPACE
        sys.modules[_NAMESPACE] = pkg


def _load_manifest(manifest_path: Path, tool_dir: Path) -> ToolManifest:
    with open(manifest_path) as f:
        data = yaml.safe_load(f) or {}
    raw_deps = data.get("dependencies", [])
    deps = [raw_deps] if isinstance(raw_deps, str) else list(raw_deps)
    return ToolManifest(
        name=data.get("name", tool_dir.name),
        slug=data.get("slug", tool_dir.name),
        description=data.get("description", ""),
        version=data.get("version", "0.1.0"),
        dependencies=deps,
    )


def _install_dependencies(deps: list[str], slug: str) -> None:
    """Install tool-declared pip dependencies before the tool module is imported."""
    if not deps:
        return
    # Prefer uv (faster); fall back to the current interpreter's pip.
    if shutil.which("uv"):
        installer = shutil.which("uv")
        cmd = ["uv", "pip", "install", "--quiet", *deps]
    else:
        installer = sys.executable
        cmd = [sys.executable, "-m", "pip", "install", "--quiet", *deps]
    logger.info("deps install : [%s] %s  via %s", slug, ", ".join(deps), installer)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Dependency installation failed for tool '{slug}':\n{result.stderr.strip()}"
        )
    logger.info("deps OK      : [%s]", slug)


def _import_tool_module(slug: str, tool_dir: Path) -> types.ModuleType:
    """Dynamically import ``tool_dir/__init__.py`` under the apik_tools namespace."""
    _ensure_namespace()
    module_name = f"{_NAMESPACE}.{slug}"

    spec = importlib.util.spec_from_file_location(
        module_name,
        tool_dir / "__init__.py",
        submodule_search_locations=[str(tool_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for tool '{slug}'")

    module = importlib.util.module_from_spec(spec)
    module.__package__ = module_name
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _patch_templates(module: types.ModuleType, tool_dir: Path) -> None:
    """
    Extend the tool's Jinja2 environment so it can also resolve templates from
    the main app (e.g. ``{% extends "base.html" %}``).

    Lookup order: tool root → tool/templates/ → main app templates.
    """
    tmpl: Jinja2Templates | None = getattr(module, "templates", None)
    if tmpl is None:
        return

    extra_dirs = [str(tool_dir / "templates"), str(MAIN_TEMPLATES_DIR)]
    existing_loader = tmpl.env.loader

    if existing_loader is None:
        tmpl.env.loader = FileSystemLoader([str(tool_dir)] + extra_dirs)
    else:
        tmpl.env.loader = ChoiceLoader(
            [existing_loader, FileSystemLoader(extra_dirs)]
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_tools(
    tools_dir: Path,
    disabled_slugs: set[str] | None = None,
) -> list[LoadedTool]:
    """
    Walk *tools_dir* and load every valid tool (directory that contains
    ``manifest.yml``, ``__init__.py``, and ``index.html``).

    Tools whose slug appears in *disabled_slugs* are silently skipped.
    """
    logger.info("━" * 48)
    logger.info("tools_dir    : %s", tools_dir)

    if not tools_dir.is_dir():
        logger.warning("tools_dir does not exist — no tools loaded")
        return []

    disabled_slugs = disabled_slugs or set()
    loaded: list[LoadedTool] = []
    failed_count = 0

    all_dirs = sorted(d for d in tools_dir.iterdir() if d.is_dir())
    logger.info("candidates   : %d director%s", len(all_dirs), "y" if len(all_dirs) == 1 else "ies")

    for tool_dir in all_dirs:
        missing = [
            name
            for name in ("manifest.yml", "__init__.py", "index.html")
            if not (tool_dir / name).exists()
        ]
        if missing:
            logger.debug("skip %-16s  missing: %s", tool_dir.name, ", ".join(missing))
            continue  # not a valid tool directory

        try:
            manifest = _load_manifest(tool_dir / "manifest.yml", tool_dir)

            if manifest.slug in disabled_slugs:
                logger.info("disabled     : [%s] %s v%s", manifest.slug, manifest.name, manifest.version)
                continue

            _install_dependencies(manifest.dependencies, manifest.slug)
            module = _import_tool_module(manifest.slug, tool_dir)
            _patch_templates(module, tool_dir)

            router: APIRouter | None = getattr(module, "router", None)
            if not isinstance(router, APIRouter):
                raise TypeError(
                    f"Tool '{tool_dir.name}' must expose an "
                    f"``APIRouter`` as ``router`` (got {type(router).__name__})"
                )

            deps_info = f"  deps: {len(manifest.dependencies)}" if manifest.dependencies else ""
            logger.info(
                "loaded       : [%s] %s v%s  →  /tools/%s/  (%s)%s",
                manifest.slug, manifest.name, manifest.version,
                manifest.slug, manifest.description, deps_info,
            )
            loaded.append(LoadedTool(manifest=manifest, router=router, tool_dir=tool_dir))
        except Exception as exc:
            logger.error("FAILED       : [%s]  %s", tool_dir.name, exc)
            failed_count += 1

    logger.info("━" * 48)
    logger.info(
        "tools        : %d loaded  |  %d disabled  |  %d failed",
        len(loaded),
        len([d for d in all_dirs if _slug_of(d) in disabled_slugs]),
        failed_count,
    )
    logger.info("━" * 48)
    return loaded


def _slug_of(tool_dir: Path) -> str:
    """Return the slug for a tool directory, or the dir name if manifest is missing."""
    manifest_path = tool_dir / "manifest.yml"
    if not manifest_path.exists():
        return tool_dir.name
    try:
        with open(manifest_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("slug", tool_dir.name)
    except Exception:
        return tool_dir.name


def register_tools(app: FastAPI, tools: list[LoadedTool]) -> None:
    """Mount every loaded tool's router (and optional static files) onto *app*."""
    reg_logger = logging.getLogger("apik.tools")
    for tool in tools:
        prefix = f"/tools/{tool.manifest.slug}"
        app.include_router(tool.router, prefix=prefix)
        reg_logger.info("route        : GET  %s/  →  [%s]", prefix, tool.manifest.slug)

        static_dir = tool.tool_dir / "static"
        if static_dir.is_dir():
            mount_path = f"/static/tools/{tool.manifest.slug}"
            app.mount(
                mount_path,
                StaticFiles(directory=str(static_dir)),
                name=f"static_tool_{tool.manifest.slug}",
            )
            reg_logger.info("static       : %s  →  %s", mount_path, static_dir)
