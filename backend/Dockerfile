FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade "pip==24.3.1" \
    && pip install .

COPY alembic.ini ./
COPY alembic ./alembic

RUN addgroup --system imperium \
    && adduser --system --ingroup imperium --home /app --no-create-home imperium \
    && chown -R imperium:imperium /app

USER imperium

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
