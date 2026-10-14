FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AEROBOOKING_SQLITE_PATH=/app/data/aerobooking.db
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && mkdir -p /app/data

EXPOSE 8000
VOLUME ["/app/data"]
CMD ["python", "-m", "uvicorn", "aerobooking.api:app", "--host", "0.0.0.0", "--port", "8000"]
