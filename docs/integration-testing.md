# PostgreSQL and Redis integration testing

`docker-compose.integration.yml` runs only PostgreSQL and Redis, independently of the development Compose project. Ports bind to `127.0.0.1:15432` and `127.0.0.1:16379`. Both services use disposable storage; no persistent volumes are created. Do not point these tests at shared services: tests clear the cache and the outage test stops Redis.

Use an activated project virtual environment and set process environment variables (do not replace your local `.env`):

| Variable | Value |
| --- | --- |
| `SECRET_KEY` | A newly generated temporary key |
| `DEBUG` | `True` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` |
| `DB_ENGINE` | `postgresql` |
| `POSTGRES_DB` | `academy_integration` |
| `POSTGRES_USER` | `academy_integration` |
| `POSTGRES_PASSWORD` | A newly generated temporary password |
| `INTEGRATION_POSTGRES_PASSWORD` | The same temporary password |
| `DB_HOST` | `127.0.0.1` |
| `DB_PORT` | `15432` |
| `REDIS_URL` | `redis://127.0.0.1:16379/1` |
| `CELERY_BROKER_URL` | `redis://127.0.0.1:16379/0` |
| `CELERY_TASK_ALWAYS_EAGER` | `True` (broker tests explicitly override it) |
| `RUN_SERVICE_INTEGRATION` | `1` |
| `INTEGRATION_COMPOSE_PROJECT` | A unique name starting with `academy-integration-` |

From the repository root in PowerShell, using that project name:

```powershell
docker compose -f docker-compose.integration.yml -p $env:INTEGRATION_COMPOSE_PROJECT up -d --wait postgres redis
python -B manage.py check
python -B manage.py migrate --noinput
python -B manage.py makemigrations --check --dry-run
python -B manage.py migrate --check
python -B -m pytest -p no:cacheprovider -q --tb=short
python -B -m pytest tests/test_regressions.py::test_concurrent_comment_cooldown_postgresql -p no:cacheprovider -q --tb=short
```

Always shut down the temporary project after testing, including when a test fails:

```powershell
docker compose -f docker-compose.integration.yml -p $env:INTEGRATION_COMPOSE_PROJECT down
```

Restore or unset the process variables afterward. No real `.env` credentials are required. Django creates a separate `test_academy_integration` database for pytest.

The opt-in tests in `tests/test_service_integration.py` verify real Redis TTLs, endpoint expiry, Celery publishing, controlled cache failures, post-commit broker failures, and service recovery. The outage test checks the Compose project label before stopping Redis and restarts it in a `finally` block. Celery publishing is verified by consuming and acknowledging the broker message directly; no worker or Beat is started. Worker execution, automatic retry/delivery guarantees, Beat scheduling, and production load/failover are outside this validation.

Without `RUN_SERVICE_INTEGRATION=1`, the three service tests are explicitly skipped. SQLite also skips the PostgreSQL row-locking test.
