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

# ---------------------------------------------------------------------------
# Runtime configuration — all values can be overridden at `docker run` time
# with -e APIK_HOST=... or via an env_file / compose environment block.
# ---------------------------------------------------------------------------
ARG  APIK_HOST=0.0.0.0
ARG  APIK_PORT=8000
ARG  APIK_WORKERS=1
ARG  APIK_RELOAD=false
ARG  APIK_TOOLS_DIR=/app/tools
ARG  APIK_DISABLED_TOOLS=""

ENV  APIK_HOST=${APIK_HOST}
ENV  APIK_PORT=${APIK_PORT}
ENV  APIK_WORKERS=${APIK_WORKERS}
ENV  APIK_RELOAD=${APIK_RELOAD}
ENV  APIK_TOOLS_DIR=${APIK_TOOLS_DIR}
ENV  APIK_DISABLED_TOOLS=${APIK_DISABLED_TOOLS}

EXPOSE ${APIK_PORT}

CMD ["sh", "-c", \
     "uvicorn src.main:app --host $APIK_HOST --port $APIK_PORT --workers $APIK_WORKERS"]