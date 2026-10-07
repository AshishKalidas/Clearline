FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
COPY evals ./evals
COPY mcp_server ./mcp_server
RUN pip install --no-cache-dir '.[dev]'
COPY . .
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
