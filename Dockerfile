FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config.yaml ./config.yaml
COPY artifacts ./artifacts
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "fouling.api:app", "--host", "0.0.0.0", "--port", "8000"]
