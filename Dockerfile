FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    curl \
    nodejs \
    npm \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY core/ ./core/
RUN uv pip install --system --no-cache .

# Install Node dependencies
COPY package.json ./
RUN npm install

# Copy remaining files and build CSS
COPY . .
RUN npm run css:build

# Create system-level config with Docker-appropriate defaults.
# All values can still be overridden at runtime via APIK_* environment variables.
RUN mkdir -p /etc/apik && printf '%s\n' \
    'host: "0.0.0.0"' \
    'port: 8000' \
    'workers: 1' \
    'reload: false' \
    'tools_dir: "/app/tools"' \
    > /etc/apik/apik.yml

EXPOSE 8000

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["start"]