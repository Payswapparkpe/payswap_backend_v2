# Run processes from backend/ (Django project root). Repo root is the monorepo.
web: bash -c 'cd backend && exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}'
# Single worker consumes all queues (backward compatible). For production, run dedicated workers per queue (see docs/PRODUCTION_CELERY_QUEUES.md).
worker: bash -c 'cd backend && exec celery -A core worker -l info -Q default,api_log,notifications,voucher'
beat: bash -c 'cd backend && exec celery -A core beat -l info'
