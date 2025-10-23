FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for building wheels and PostgreSQL client libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package/deps manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy dependency metadata and pre-sync env to leverage Docker layer cache
COPY pyproject.toml ./
RUN uv sync --no-dev

# Copy application source
COPY . .

# Default command
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
