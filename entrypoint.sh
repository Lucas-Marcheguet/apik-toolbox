#!/bin/bash
# entrypoint.sh
cd /app
npm exec -- tailwindcss -i core/static/css/input.css -o core/static/css/tailwind.css --minify
exec "$@"