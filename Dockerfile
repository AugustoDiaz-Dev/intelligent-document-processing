# Doc Processing System — production image
FROM python:3.12-slim

WORKDIR /app

# Application code and project config (needed for pip install)
COPY pyproject.toml ./
COPY app/ ./app/

# Install dependencies (no dev extras for smaller image)
RUN pip install --no-cache-dir -e .

# Run with PORT from environment (Railway/Render/Fly set this)
ENV PORT=8000
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
