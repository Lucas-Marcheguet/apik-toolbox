# apik-toolbox

A web application built with **FastAPI**, **Jinja2**, **HTMX**, **Alpine.js**, **Tailwind CSS**, and **DaisyUI**.

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
