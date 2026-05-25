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
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import yaml
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

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
    return ToolManifest(
        name=data.get("name", tool_dir.name),
        slug=data.get("slug", tool_dir.name),
        description=data.get("description", ""),
        version=data.get("version", "0.1.0"),
    )


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
    if not tools_dir.is_dir():
        print(f"[tool_manager] tools_dir '{tools_dir}' does not exist — skipping.")
        return []

    disabled_slugs = disabled_slugs or set()
    loaded: list[LoadedTool] = []

    for tool_dir in sorted(tools_dir.iterdir()):
        if not tool_dir.is_dir():
            continue

        missing = [
            name
            for name in ("manifest.yml", "__init__.py", "index.html")
            if not (tool_dir / name).exists()
        ]
        if missing:
            continue  # not a valid tool directory

        try:
            manifest = _load_manifest(tool_dir / "manifest.yml", tool_dir)

            if manifest.slug in disabled_slugs:
                print(f"[tool_manager] Skipping disabled tool '{manifest.slug}'")
                continue

            module = _import_tool_module(manifest.slug, tool_dir)
            _patch_templates(module, tool_dir)

            router: APIRouter | None = getattr(module, "router", None)
            if not isinstance(router, APIRouter):
                raise TypeError(
                    f"Tool '{tool_dir.name}' must expose an "
                    f"``APIRouter`` as ``router`` (got {type(router).__name__})"
                )

            loaded.append(LoadedTool(manifest=manifest, router=router, tool_dir=tool_dir))
            print(f"[tool_manager] Loaded tool '{manifest.name}' at /tools/{manifest.slug}/")
        except Exception as exc:
            print(f"[tool_manager] Failed to load tool '{tool_dir.name}': {exc}")

    return loaded


def register_tools(app: FastAPI, tools: list[LoadedTool]) -> None:
    """Mount every loaded tool's router (and optional static files) onto *app*."""
    for tool in tools:
        prefix = f"/tools/{tool.manifest.slug}"
        app.include_router(tool.router, prefix=prefix)

        static_dir = tool.tool_dir / "static"
        if static_dir.is_dir():
            app.mount(
                f"/static/tools/{tool.manifest.slug}",
                StaticFiles(directory=str(static_dir)),
                name=f"static_tool_{tool.manifest.slug}",
            )
