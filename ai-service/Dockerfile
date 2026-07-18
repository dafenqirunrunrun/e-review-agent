FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    E_REVIEW_MODEL_MODE=base \
    E_REVIEW_ADAPTER_ENABLED=false

WORKDIR /app

RUN addgroup --system ereview && adduser --system --ingroup ereview ereview

COPY ai-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ai-service/app /app/app

USER ereview

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8008/api/v1/health', timeout=3).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
