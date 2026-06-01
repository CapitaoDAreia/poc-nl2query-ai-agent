FROM ghcr.io/astral-sh/uv:python3.11-alpine

WORKDIR /app

ENV UV_LINK_MODE=copy

COPY pyproject.toml /app/

RUN uv pip install --system --requirement pyproject.toml

COPY . /app

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "api.api_ingest:app", "--host", "0.0.0.0", "--port", "8001"]