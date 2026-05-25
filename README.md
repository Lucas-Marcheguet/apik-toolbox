# apik-toolbox

An extensible internal web toolbox built with **FastAPI**, **Jinja2**, **HTMX**, **Alpine.js**, **Tailwind CSS**, and **DaisyUI**.

Tools are self-contained plug-ins dropped into a `tools/` directory — no core changes needed to add, remove, or update them.

---

## Contents

- [Stack](#stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Running](#running)
- [Docker](#docker)
- [Creating a tool](#creating-a-tool)
- [PWA & error pages](#pwa--error-pages)

---

## Stack

| Layer | Technology |
|---|---|
| Web framework | [FastAPI](https://fastapi.tiangolo.com) |
| Templates | [Jinja2](https://jinja.palletsprojects.com) |
| Interactivity | [HTMX](https://htmx.org) + [Alpine.js](https://alpinejs.dev) |
| Styling | [Tailwind CSS v3](https://tailwindcss.com) + [DaisyUI v4](https://daisyui.com) |
| Runtime | Python 3.12, managed by [uv](https://docs.astral.sh/uv) |

---

## Project structure

```
apik.yml             # Runtime configuration
tools/               # Drop-in tool plug-ins
core/
├── main.py          # FastAPI app entry point
├── cli.py           # `dev` and `start` entry points
├── config.py        # Pydantic config model + apik.yml loader
├── services/
│   └── tool_manager.py  # Tool discovery and router registration
├── templates/       # base.html, index.html, 404.html
└── static/
    ├── css/         # input.css (source) → tailwind.css (generated, do not edit)
    ├── img/
    ├── js/
    ├── manifest.json
    └── sw.js
tailwind.config.js
package.json
pyproject.toml
Dockerfile
compose.yml
```

---

## Getting started

**Requirements:** [uv](https://docs.astral.sh/uv/getting-started/installation/) · [Node.js](https://nodejs.org)

```bash
uv sync        # create .venv and install Python deps
npm install    # install Tailwind CLI and DaisyUI
```

---

## Configuration

Config is resolved in priority order (highest first):

1. **CLI flags** — e.g. `uv run start --host 0.0.0.0 --workers 4`
2. **`APIK_*` environment variables**
3. **`/etc/apik/apik.yml`** — system-level config (Docker default)
4. **`./apik.yml`** — local project config (dev default)
5. **Built-in defaults**

All keys are optional:

```yaml
host: "127.0.0.1"      # APIK_HOST     — default: 127.0.0.1
port: 8000              # APIK_PORT     — default: 8000
workers: 1              # APIK_WORKERS  — default: 1 (ignored in reload mode)
reload: false           # APIK_RELOAD   — default: false
tools_dir: "./tools"    # APIK_TOOLS_DIR — relative paths resolved from this file
disabled_tools:         # APIK_DISABLED_TOOLS (comma-separated in env)
  - example
```

The config is loaded once at startup — restart to apply changes.

---

## Running

```bash
uv run dev    # uvicorn --reload + Tailwind watcher
uv run start  # production server (reads from config)
```

CLI flags override config and env vars:

```bash
uv run start --host 0.0.0.0 --port 9000 --workers 4 --tools-dir /srv/tools
uv run start --disabled-tools example,legacy_tool
uv run dev   --tools-dir ./my-tools
```

---

## Docker

```bash
docker build -t apik-toolbox .
docker run -p 8000:8000 apik-toolbox
```

The image ships with `/etc/apik/apik.yml` pre-configured for containers (`host: 0.0.0.0`, `tools_dir: /app/tools`). Override it in two ways:

**Mount a config file:**
```bash
docker run -p 8000:8000 \
  -v $(pwd)/apik.yml:/etc/apik/apik.yml:ro \
  apik-toolbox
```
Use absolute paths for `tools_dir` inside the container (e.g. `/app/tools`).

**Environment variables** (applied after the config file, always win):
```bash
docker run -p 9000:9000 -e APIK_PORT=9000 -e APIK_WORKERS=4 apik-toolbox
```

| Variable | Container default | Description |
|---|---|---|
| `APIK_HOST` | `0.0.0.0` | Bind address |
| `APIK_PORT` | `8000` | Listen port |
| `APIK_WORKERS` | `1` | Uvicorn worker processes |
| `APIK_RELOAD` | `false` | Auto-reload |
| `APIK_TOOLS_DIR` | `/app/tools` | Tools directory |
| `APIK_DISABLED_TOOLS` | _(empty)_ | Comma-separated slugs to skip |

**Mount a tools directory** (avoids rebuilding the image):
```bash
docker run -p 8000:8000 -v $(pwd)/tools:/app/tools:ro apik-toolbox
```

**Docker Compose:**
```bash
docker compose up
```
Customise with a `.env` file next to `compose.yml` (`APIK_PORT=9000`, `APIK_WORKERS=4`, …).

---

## Creating a tool

A tool is a directory inside `tools_dir`:

```
tools/
└── my_tool/
    ├── manifest.yml   ← required: metadata
    ├── __init__.py    ← required: must expose `router: APIRouter`
    ├── index.html     ← required: entry-point template
    ├── views/         ← optional: additional templates
    └── static/        ← optional: auto-mounted at /static/tools/<slug>/
```

**`manifest.yml`**
```yaml
name: "My Tool"
slug: "my_tool"           # URL prefix — defaults to directory name
description: "Does something useful."
version: "1.0.0"
```

**`__init__.py`**
```python
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent))
router = APIRouter()

@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"active_view": "home"})
```

The tool is mounted at `/tools/<slug>/`. `{% extends "base.html" %}` resolves to the main app's shared layout automatically.

**Sub-routers:** add an `APIRouter(prefix="/api")` into `router` — reachable at `/tools/<slug>/api/…`

**Static files:** place assets in `my_tool/static/`, served at `/static/tools/<slug>/`

**Template lookup:** tool root → `tool/templates/` → `core/templates/` (provides `base.html`, `404.html`, …)

---

## PWA & error pages

The app ships as a PWA: `/manifest.json` and `/sw.js` (cache-first for static assets, network-first for navigation). Install via the browser's "Add to Home Screen" prompt.

Unknown routes return a branded 404 page (`core/templates/404.html`). Add handlers for other status codes in `core/main.py`:

```python
@app.exception_handler(500)
async def server_error(request: Request, _: HTTPException):
    return templates.TemplateResponse(request, "500.html", status_code=500)
```
