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
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Install Node dependencies
COPY package.json tailwind.config.js ./
RUN npm install

# Copy remaining files and build CSS
COPY . .
RUN npm run css:build

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]