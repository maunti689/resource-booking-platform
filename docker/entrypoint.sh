#!/bin/sh
set -eu

case "${1:-api}" in
  api)
    python manage.py migrate --noinput
    exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000
    ;;
  worker)
    exec celery -A config worker --loglevel="${LOG_LEVEL:-INFO}"
    ;;
  beat)
    exec celery -A config beat \
      --loglevel="${LOG_LEVEL:-INFO}" \
      --schedule=/tmp/celerybeat-schedule
    ;;
  *)
    exec "$@"
    ;;
esac
