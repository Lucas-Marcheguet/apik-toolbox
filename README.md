# apik-toolbox

An extensible internal web toolbox built with **FastAPI**, **Jinja2**, **HTMX**, **Alpine.js**, **Tailwind CSS**, and **DaisyUI**.

Tools are self-contained plug-ins dropped into a `tools/` directory — no changes to the core app are needed to add, remove, or update them.

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
apik.yml             # Runtime configuration (host, port, workers, tools_dir…)
tools/               # Drop-in tool plug-ins (see "Creating a tool" below)
core/
├── main.py          # FastAPI app — mounts static files, templates, and tools
├── cli.py           # Entry points: `dev` and `start`
├── config.py        # Pydantic config model + apik.yml loader
├── routers/         # Core app routers (if needed)
├── models/          # Pydantic models / DB schemas
├── services/
│   └── tool_manager.py  # Tool discovery, dynamic import, router registration
├── templates/
│   ├── base.html    # Shared layout (navbar, PWA tags, theme)
│   ├── index.html   # Tool launcher dashboard
│   └── 404.html     # Custom 404 page
└── static/
    ├── css/
    │   ├── input.css      # Tailwind source — edit this to add custom styles
    │   └── tailwind.css   # Generated output — do not edit manually
    ├── img/               # Logo and other images
    ├── js/                # HTMX and other scripts
    ├── manifest.json      # PWA web app manifest
    └── sw.js              # Service worker (cache-first for static assets)
tailwind.config.js   # Tailwind content paths, DaisyUI theme
package.json         # Node toolchain (Tailwind CLI + DaisyUI)
pyproject.toml       # Python dependencies and project scripts
Dockerfile           # Production image
compose.yml          # Docker Compose for deployment
```

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Node.js](https://nodejs.org) (for the Tailwind CSS build)

## Setup

```bash
uv sync        # create .venv and install Python dependencies
npm install    # install Tailwind CLI and DaisyUI
```

---

## Configuration — `apik.yml`

Place `apik.yml` at the project root (next to `pyproject.toml`). All keys are optional.

```yaml
host: "127.0.0.1"      # APIK_HOST     — default: 127.0.0.1
port: 8000              # APIK_PORT     — default: 8000
workers: 1              # APIK_WORKERS  — default: 1 (ignored in dev/reload mode)
reload: false           # APIK_RELOAD   — default: false

# Directory scanned for tool plug-ins.
# Relative paths are resolved from this file's location.
tools_dir: "./tools"    # APIK_TOOLS_DIR

# Comma-separated list of tool slugs to skip at startup.
# disabled_tools:       # APIK_DISABLED_TOOLS
#   - example
```

Every key can also be set (or overridden) via the matching `APIK_*` environment
variable — env vars take precedence over the file. This is the intended mechanism
for Docker/CI deployments (see `compose.yml`).

The config is loaded once at startup. Restart the server to apply changes.

---

## Running

### Development (hot-reload + Tailwind watcher)

```bash
uv run dev
```

Starts **uvicorn** with `--reload` on the configured host/port, and the **Tailwind
CSS watcher** in parallel. One command for the full dev loop.

### Production

```bash
uv run start
```

Uses `workers`, `host`, `port`, and `reload` from `apik.yml` (or `APIK_*` env vars).

---

## PWA

The app ships as a Progressive Web App out of the box:

- **`/manifest.json`** — web app manifest (name, icons, theme colour, standalone display)
- **`/sw.js`** — service worker registered by `base.html` on `window load`:
  - Cache-first for all `/static/` assets (CSS, JS, images)
  - Network-first for navigation and API calls
  - Old cache versions are pruned on activation

To install the app on mobile or desktop, use the browser's "Add to Home Screen" /
"Install" prompt.

---

## Error pages

Unknown routes return a branded **404** page (`core/templates/404.html`).
To add handlers for other status codes follow the same pattern in `core/main.py`:

```python
@app.exception_handler(500)
async def server_error(request: Request, _: HTTPException):
    return templates.TemplateResponse(request, "500.html", status_code=500)
```

---

## Creating a tool

A tool is a directory inside `tools_dir` that satisfies the following contract:

```
tools/
└── my_tool/              ← directory name used as default slug
    ├── manifest.yml      ← required: tool metadata
    ├── __init__.py       ← required: must expose `router: APIRouter`
    ├── index.html        ← required: entry-point template
    ├── views/            ← optional: additional view templates
    │   └── detail.html
    └── static/           ← optional: auto-mounted at /static/tools/<slug>/
        └── ...
```

### 1. `manifest.yml`

```yaml
name: "My Tool"
slug: "my_tool"           # URL prefix: /tools/my_tool/ — defaults to dir name
description: "Does something useful."
version: "1.0.0"
```

### 2. `__init__.py`

Must expose a `router` attribute of type `fastapi.APIRouter`.

```python
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

TOOL_DIR = Path(__file__).parent

# Jinja2Templates is patched at load time so `{% extends "base.html" %}` resolves
# to the main app's base template automatically.
templates = Jinja2Templates(directory=str(TOOL_DIR))

router = APIRouter()


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"active_view": "home"})


@router.get("/view/detail")
async def detail(request: Request):
    """Allows direct-URL / bookmarked access with the correct tab pre-selected."""
    return templates.TemplateResponse(request, "index.html", {"active_view": "detail"})
```

The tool manager mounts this router at `/tools/<slug>/`, so the route above is
reachable at `GET /tools/my_tool/`.

### 3. `index.html`

The entry point for the tool. Extends `base.html`, owns all navigation between its
views, and uses **Alpine.js** to switch tabs client-side without a page reload.

The `active_view` context variable (set server-side) initialises Alpine's state so
direct URL navigation pre-selects the correct tab.

```html
{% extends "base.html" %}

{% block title %}My Tool — Apik Toolbox{% endblock %}

{# Optional breadcrumb injected into the shared top navbar #}
{% block navbar_extra %}
<div class="flex items-center gap-1.5 text-sm ml-2">
    <span class="text-base-content/30">/</span>
    <a href="/" class="text-base-content/50 hover:text-base-content">Toolbox</a>
    <span class="text-base-content/30">/</span>
    <span class="text-base-content font-medium">My Tool</span>
</div>
{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-6 py-8"
     x-data="{ tab: '{{ active_view or 'home' }}' }">

    <h1 class="text-xl font-bold text-base-content mb-6">My Tool</h1>

    <!-- Underline tabs — active state driven by Alpine :class binding -->
    <div class="border-b border-base-300 mb-6">
        <nav class="flex -mb-px">
            <button @click="tab = 'home'"
                    :class="tab === 'home'
                        ? 'border-primary text-primary'
                        : 'border-transparent text-base-content/50 hover:text-base-content hover:border-base-300'"
                    class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors">
                Home
            </button>
            <button @click="tab = 'detail'"
                    :class="tab === 'detail'
                        ? 'border-primary text-primary'
                        : 'border-transparent text-base-content/50 hover:text-base-content hover:border-base-300'"
                    class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors">
                Detail
            </button>
        </nav>
    </div>

    <!-- Tab panels — all rendered server-side, toggled by Alpine x-show.
         x-cloak prevents flash before Alpine hydrates (rule in input.css). -->
    <div x-show="tab === 'home'" x-cloak>
        {% include "views/home.html" %}
    </div>
    <div x-show="tab === 'detail'" x-cloak>
        {% include "views/detail.html" %}
    </div>

</div>
{% endblock %}
```

### Adding sub-routers

A tool can organise its routes into sub-routers included into its main `router`.
The tool manager only interacts with `router`, so this is entirely transparent.

```python
# In __init__.py
api_router = APIRouter(prefix="/api")

@api_router.get("/items")
async def list_items():
    return []

router.include_router(api_router)
# Reachable at GET /tools/my_tool/api/items
```

### Static files

Place any static assets (images, JS, CSS) in `my_tool/static/`. They are
automatically mounted at `/static/tools/my_tool/` when the tool is loaded.

```html
<img src="/static/tools/my_tool/logo.png">
```

### Template resolution order

When a tool calls `templates.TemplateResponse(...)`, Jinja2 looks for the template
in this order:

1. `tools/my_tool/` (tool root)
2. `tools/my_tool/templates/` (tool templates sub-folder)
3. `core/templates/` (main app — provides `base.html`, `404.html`, …)

A tool can override any shared template by placing its own copy in its root directory.

---

## Disabling tools

Add slug(s) to `disabled_tools` in `apik.yml` to skip them at startup without
deleting their directory:

```yaml
disabled_tools:
  - example
```

Or via environment variable (comma-separated):

```bash
APIK_DISABLED_TOOLS=example,legacy_tool uv run start
```

---

## Styling

All styles are centralised in `core/static/css/`:

| File | Purpose |
|---|---|
| `input.css` | Tailwind source — edit to add directives or custom rules |
| `tailwind.css` | Generated output — rebuilt by `npm run css:build` / `css:watch` |

The custom DaisyUI theme (`apik`) provides CSS variables matching the brand palette:

| Token | Usage |
|---|---|
| `primary` | brand purple — buttons, active tabs, accents |
| `secondary` | dark navy — secondary actions |
| `base-100` | white — card backgrounds |
| `base-200` | light grey — page background |
| `base-300` | border grey — dividers, borders |
| `base-content` | primary text colour |

The `[x-cloak]` rule (`display: none !important`) is included in `input.css` so
Alpine.js tab panels don't flash before the framework hydrates.


Tools are self-contained plug-ins dropped into a `tools/` directory — no changes to the core app are needed to add, remove, or update them.

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
apik.yml             # Runtime configuration (host, port, workers, tools_dir…)
tools/               # Drop-in tool plug-ins (see "Creating a tool" below)
src/
├── main.py          # FastAPI app — mounts static files, templates, and tools
├── cli.py           # Entry points: `dev` and `start`
├── config.py        # Pydantic config model + apik.yml loader
├── routers/         # Core app routers (if needed)
├── models/          # Pydantic models / DB schemas
├── services/
│   └── tool_manager.py  # Tool discovery, dynamic import, router registration
├── templates/
│   ├── base.html    # Shared layout (navbar, theme)
│   └── index.html   # Tool launcher dashboard
├── static/
│   ├── css/         # tailwind.css is generated here — do not edit manually
│   ├── img/         # Static images (logo, etc.)
│   └── js/          # HTMX and custom JS
└── styles/
    └── tailwind.css # Tailwind CSS input — add custom directives here
tailwind.config.js   # Tailwind content paths, DaisyUI theme
package.json         # Node toolchain (Tailwind CLI + DaisyUI)
pyproject.toml       # Python dependencies and project scripts
Dockerfile           # Production image
compose.yml          # Docker Compose for deployment
```

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Node.js](https://nodejs.org) (for the Tailwind CSS build)

## Setup

```bash
uv sync        # create .venv and install Python dependencies
npm install    # install Tailwind CLI and DaisyUI
```

---

## Configuration — `apik.yml`

Place `apik.yml` at the project root (next to `pyproject.toml`). All keys are optional.

```yaml
host: "127.0.0.1"   # default: 127.0.0.1
port: 8000           # default: 8000
workers: 1           # default: 1  (ignored in dev/reload mode)
reload: false        # default: false

# Directory scanned for tool plug-ins.
# Relative paths are resolved from this file's location.
tools_dir: "./tools"
```

The config is loaded once at startup via `src/config.py`. Change any value and restart the server to apply it.

---

## Running

### Development (hot-reload + Tailwind watcher)

```bash
uv run dev
```

Starts **uvicorn** with `--reload` on the configured host/port, and the **Tailwind CSS watcher** in parallel.

### Production

```bash
uv run start
```

Uses `workers`, `host`, `port`, and `reload` from `apik.yml`.

---

## Creating a tool

A tool is a directory inside `tools_dir` that satisfies the following contract:

```
tools/
└── my_tool/              ← directory name used as default slug
    ├── manifest.yml      ← required: tool metadata
    ├── __init__.py       ← required: must expose `router: APIRouter`
    ├── index.html        ← required: entry-point template
    ├── views/            ← optional: HTMX fragment templates
    │   └── detail.html
    └── static/           ← optional: auto-mounted at /static/tools/<slug>/
        └── ...
```

### 1. `manifest.yml`

```yaml
name: "My Tool"
slug: "my_tool"           # URL prefix: /tools/my_tool/ — defaults to dir name
description: "Does something useful."
version: "1.0.0"
```

### 2. `__init__.py`

Must expose a `router` attribute of type `fastapi.APIRouter`.

```python
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

TOOL_DIR = Path(__file__).parent

# Jinja2Templates is patched at load time so `{% extends "base.html" %}` resolves
# to the main app's base template automatically.
templates = Jinja2Templates(directory=str(TOOL_DIR))

router = APIRouter()


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"active_view": "home"})
```

The tool manager mounts this router at `/tools/<slug>/`, so the route above is
reachable at `GET /tools/my_tool/`.

### 3. `index.html`

The entry point for the tool. Must extend `base.html` and own navigation between all
of its views. Additional views are loaded into a shared content area via HTMX.

```html
{% extends "base.html" %}

{% block title %}My Tool — Apik Toolbox{% endblock %}

{# Optional breadcrumb in the shared top navbar #}
{% block navbar_extra %}
<div class="flex items-center gap-1.5 text-sm ml-2">
    <span class="text-base-content/30">/</span>
    <a href="/" class="text-base-content/50 hover:text-base-content">Toolbox</a>
    <span class="text-base-content/30">/</span>
    <span class="text-base-content font-medium">My Tool</span>
</div>
{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-6 py-8">

    <h1 class="text-xl font-bold mb-6">My Tool</h1>

    <!-- Tab navigation -->
    <div class="border-b border-base-300 mb-6">
        <nav class="flex -mb-px">
            <a class="px-4 py-2.5 text-sm font-medium border-b-2 cursor-pointer
                      {% if active_view == 'home' %}border-primary text-primary
                      {% else %}border-transparent text-base-content/50 hover:text-base-content{% endif %}"
               hx-get="/tools/my_tool/"
               hx-target="#view-content"
               hx-swap="innerHTML"
               hx-push-url="true">
                Home
            </a>
            <a class="px-4 py-2.5 text-sm font-medium border-b-2 cursor-pointer
                      {% if active_view == 'detail' %}border-primary text-primary
                      {% else %}border-transparent text-base-content/50 hover:text-base-content{% endif %}"
               hx-get="/tools/my_tool/view/detail"
               hx-target="#view-content"
               hx-swap="innerHTML"
               hx-push-url="true">
                Detail
            </a>
        </nav>
    </div>

    <div id="view-content">
        {% if active_view == 'home' or not active_view %}
            <!-- Home view content -->
        {% endif %}
    </div>
</div>
{% endblock %}
```

### Adding sub-routers

A tool can organise its routes into sub-routers, which are then included into
the tool's main `router`. The tool manager only interacts with `router`, so this
is entirely transparent to the framework.

```python
# In __init__.py
api_router = APIRouter(prefix="/api")

@api_router.get("/items")
async def list_items():
    return []

router.include_router(api_router)
# Reachable at GET /tools/my_tool/api/items
```

### Static files

Place any static assets (images, JS, CSS) in `my_tool/static/`. They are
automatically mounted at `/static/tools/my_tool/` when the tool is loaded.

```html
<img src="/static/tools/my_tool/logo.png">
```

### Template resolution order

When a tool calls `templates.TemplateResponse(...)`, Jinja2 looks for the template
in this order:

1. `tools/my_tool/` (tool root)
2. `tools/my_tool/templates/` (tool templates sub-folder)
3. `src/templates/` (main app — provides `base.html`)

This means a tool can override `base.html` by placing its own copy in its root
directory, but by default it inherits the shared layout.

---

## Styling

The custom DaisyUI theme (`apik`) provides CSS variables that match the brand palette.
Use the standard DaisyUI semantic colour names in templates:

| Token | Usage |
|---|---|
| `primary` | brand purple — buttons, active tabs, accents |
| `secondary` | dark navy — navbar, headings |
| `base-100` | white — card backgrounds |
| `base-200` | light grey — page background |
| `base-300` | border grey — dividers, borders |
| `base-content` | dark text |

Edit `src/styles/tailwind.css` to add custom Tailwind directives. Run `npm run css:watch` (or `uv run dev`) to rebuild.


## Stack

| Layer | Technology |
|---|---|
| Web framework | [FastAPI](https://fastapi.tiangolo.com) |
| Templates | [Jinja2](https://jinja.palletsprojects.com) |
| Interactivity | [HTMX](https://htmx.org) + [Alpine.js](https://alpinejs.dev) |
| Styling | [Tailwind CSS v3](https://tailwindcss.com) + [DaisyUI v4](https://daisyui.com) |
| Runtime | Python 3.12, managed by [uv](https://docs.astral.sh/uv) |

## Project structure

```
src/
├── main.py          # FastAPI app, mounts static files and templates
├── cli.py           # Entry point for `uv run dev`
├── routers/         # Add APIRouter modules here
├── models/          # Pydantic models / DB schemas
├── services/        # Business logic, external API calls
├── templates/
│   ├── base.html    # Base layout (HTMX, Alpine.js, Tailwind loaded here)
│   └── index.html   # Extends base.html
├── static/
│   ├── css/         # tailwind.css is generated here — do not edit manually
│   └── js/          # Place custom JS files here
└── styles/
    └── tailwind.css # Tailwind CSS input file — edit this to add custom styles
tailwind.config.js   # Tailwind content paths and DaisyUI plugin
package.json         # Node toolchain (Tailwind CLI + DaisyUI)
pyproject.toml       # Python dependencies and project scripts
Dockerfile           # Production image
compose.yml          # Docker Compose for deployment
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Node.js](https://nodejs.org) (for the Tailwind CSS build)

## Setup

```bash
uv sync        # create .venv and install Python dependencies
npm install    # install Tailwind CLI and DaisyUI
```

## Development

```bash
uv run dev
```

This single command starts both:
- **uvicorn** on `http://127.0.0.1:8000` with hot reload
- **Tailwind CSS watcher** that rebuilds `src/static/css/tailwind.css` on every template change

## Adding a new page

1. Create a template in `src/templates/`:
   ```html
   {% extends "base.html" %}
   {% block content %}
   <p>Hello</p>
   {% endblock %}
   ```

2. Add a route in `src/main.py` (or a new router module):
   ```python
   @app.get("/about")
   async def about(request: Request):
       return templates.TemplateResponse(request, "about.html")
   ```

## Adding a router

1. Create `src/routers/items.py`:
   ```python
   from fastapi import APIRouter

   router = APIRouter(prefix="/items", tags=["items"])

   @router.get("/")
   async def list_items():
       return []
   ```

2. Register it in `src/main.py`:
   ```python
   from src.routers import items
   app.include_router(items.router)
   ```

## Styling

- Edit `src/styles/tailwind.css` to add custom CSS or Tailwind directives.
- Use [DaisyUI components](https://daisyui.com/components) directly in templates via class names (e.g. `btn`, `card`, `navbar`).
- Change the DaisyUI theme by editing the `data-theme` attribute on `<html>` in `src/templates/base.html`.

## Deployment

```bash
docker compose up --build
```

The Docker build:
1. Installs Python dependencies via `pip install .`
2. Installs Node dependencies via `npm install`
3. Builds and minifies CSS via `npm run css:build`
4. Starts uvicorn on port 8000
