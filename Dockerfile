# API image (FastAPI + OR-Tools). Build from the repo root: docker build -t waterloo-electric-api .
FROM python:3.12-slim
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/src apps/api/src
COPY data/processed data/processed
COPY data/world_packs data/world_packs
COPY data/fixtures data/fixtures
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.30" "pydantic>=2.7" "pandas>=2.2" "numpy>=1.26" "pyarrow>=16" "ortools>=9.10" "openai>=1.50"
WORKDIR /app/apps/api
ENV PORT=8000
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
