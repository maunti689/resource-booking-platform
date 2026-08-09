FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY apps ./apps
COPY config ./config
RUN pip wheel --wheel-dir /wheels .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/app/.local/bin:$PATH"

RUN addgroup --system app && adduser --system --ingroup app --home /home/app app

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY --chown=app:app manage.py ./
COPY --chown=app:app apps ./apps
COPY --chown=app:app config ./config
COPY --chown=app:app docker ./docker
COPY --chown=app:app scripts ./scripts
RUN chmod +x docker/entrypoint.sh

USER app
EXPOSE 8000

ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["api"]
