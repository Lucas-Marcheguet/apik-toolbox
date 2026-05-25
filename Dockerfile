FROM python:3.12-alpine

WORKDIR /app

# System dependencies
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    python3-dev \
    cargo \
    nodejs \
    npm

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY core/ ./core/
RUN pip install --no-cache-dir .

# Install Node dependencies
COPY package.json tailwind.config.js ./
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

CMD ["start"]