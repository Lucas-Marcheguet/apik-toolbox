import subprocess

import uvicorn


def dev() -> None:
    tailwind = subprocess.Popen(["npm", "run", "css:watch"])
    try:
        uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
    finally:
        tailwind.terminate()
