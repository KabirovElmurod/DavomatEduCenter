FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN pip install uv

COPY pyproject.toml ./
COPY app ./app
RUN uv pip install --system -e .

COPY . .

# Install dev dependencies for testing
RUN uv pip install --system pytest pytest-asyncio

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
