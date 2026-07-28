FROM python:3.11-slim

WORKDIR /app

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home --shell /bin/bash appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/sample_sops/ data/sample_sops/

RUN mkdir -p /app/data/processed /app/data/raw /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /app /home/appuser

USER appuser

EXPOSE 8000 8501

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
