# Django Academy — Online Learning Platform

## Project overview

Django Academy is a server-rendered Django learning platform for browsing courses, watching embedded YouTube lessons, and discussing lessons with other learners. This personal project brings together Django authentication, PostgreSQL, Redis, and Celery with both a Windows local-development setup and a Docker Compose environment.

## Main features

- Course catalog and course detail pages with ordered lessons.
- Embedded YouTube lessons with free/full-account content access checks.
- User registration, login, logout, and password-reset views.
- User profiles with avatar uploads and automatic image resizing.
- Course creation for users with author permissions and for superusers.
- Authenticated lesson comments, comment pagination, and a per-user comment cooldown.
- Redis-backed course view counters and request limiting.
- Celery background tasks for new-course email announcements.
- Celery Beat scheduling for expired-session cleanup.
- Django admin for managing courses, lessons, comments, and user profiles.

## Screenshots

Screenshots will be added here. Store manually captured images in [`docs/images/`](docs/images/) and uncomment the corresponding Markdown below when each file exists.

<!-- ![Course catalog](docs/images/course-catalog.png) -->
<!-- ![Course details and lesson list](docs/images/course-detail.png) -->
<!-- ![Video lesson and comments](docs/images/lesson-comments.png) -->
<!-- ![User profile and avatar](docs/images/user-profile.png) -->

Use demonstration accounts and avoid including personal information in screenshots.

## Tech stack

| Area | Technologies |
| --- | --- |
| Backend | Python 3.14 in Docker, Django 6.0.7 |
| Database | SQLite for local development; PostgreSQL 15 and psycopg2 for Docker |
| Cache and task broker | Local-memory cache for local development; Redis for shared caching and queued tasks |
| Background processing | Celery 5.6.3, Celery Beat |
| Frontend | Django templates, HTML, CSS, Bootstrap 5.3.3, Bootstrap Icons |
| Image processing | Pillow |
| Configuration and request limiting | django-environ, django-ratelimit, custom middleware |
| Tests | pytest, pytest-django, pytest-cov |
| Development infrastructure | Docker, Docker Compose, GitHub Actions |

Python dependencies are pinned in [`requirements.txt`](requirements.txt). The application uses Django views and templates; it does not expose a REST API.

## Project structure

```text
django_academi/
├── DjangoStore/           # Django configuration, middleware, Celery setup
├── courses/               # Course, lesson, comment models; views; tasks; tests
│   └── migrations/
├── users/                 # Registration, profiles, signals, authentication routes
│   └── migrations/
├── templates/             # Shared layout and server-rendered pages
├── static/css/            # Application styles
├── pictures/              # Default image and uploaded media
├── docs/images/           # README screenshots
├── .github/workflows/     # Test and manual test-deployment workflows
├── .env.example           # Example local configuration
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── pytest.ini
└── requirements.txt
```

## Prerequisites

For local Windows development:

- Python 3.14 (the version validated for this project) and Git.
- PowerShell and a virtual environment.
- No PostgreSQL, Redis, Celery worker, or Docker service is required for the default local mode.

For Docker, install Docker with Compose v2. Ports `8000`, `5432`, and `6379` must be available. External frontend assets and YouTube videos require internet access.

Run commands from the repository root, alongside `manage.py`.

## Environment setup

Create a virtual environment if one does not already exist, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` in place of `python` in the commands below; changing system execution policy is unnecessary.

For a **new checkout only**, copy the example and replace its secret placeholder:

```powershell
Copy-Item .env.example .env
python -c "from pathlib import Path; import secrets; p=Path('.env'); p.write_text(p.read_text().replace('replace-with-a-generated-secret-key', secrets.token_urlsafe(64)))"
```

Do not overwrite an existing `.env`. The local `.env` is ignored by Git. Configuration uses `django-environ`; process environment variables take precedence over `.env`.

| Variable | Local development value / purpose |
| --- | --- |
| `SECRET_KEY` | A unique generated secret, never committed |
| `DEBUG` | `True` for local development; defaults to `False` if omitted |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` |
| `DB_ENGINE` | `sqlite` locally, or `postgresql` |
| `SQLITE_NAME` | `db.local.sqlite3`, resolved relative to the repository root |
| `POSTGRES_DB` | PostgreSQL database name; needed only in PostgreSQL/Docker mode |
| `POSTGRES_USER` | PostgreSQL user; needed only in PostgreSQL/Docker mode |
| `POSTGRES_PASSWORD` | Your PostgreSQL password; no built-in credential |
| `DB_HOST` | `127.0.0.1` for a local PostgreSQL server |
| `DB_PORT` | `5432` |
| `REDIS_URL` | Empty for local-memory caching; `redis://127.0.0.1:6379/1` for local Redis |
| `CELERY_TASK_ALWAYS_EAGER` | `True` locally; tasks run synchronously |
| `CELERY_BROKER_URL` | Empty locally; `redis://127.0.0.1:6379/0` for queued tasks |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` |

SQLite is a development-only option because the current models and migrations use portable Django fields and constraints, with no PostgreSQL-specific queries found. It uses a separate database; the legacy `db.sqlite3` is preserved and not automatically imported. SQLite does not substitute for PostgreSQL integration testing and is rejected when `DEBUG=False`.

With an empty `REDIS_URL` and `DEBUG=True`, counters and request limits use a process-local cache. They reset on restart and are not shared between server processes. This fallback is not suitable for production. A configured but unavailable Redis server is not silently ignored. See [Django's cache documentation](https://docs.djangoproject.com/en/6.0/topics/cache/#local-memory-caching).

Eager Celery tasks execute in the web process without a worker or external broker; they are not background execution in this mode. See [Celery's eager-task configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-always-eager). Scheduled cleanup requires Beat and a worker in the asynchronous setup; locally you can run `python manage.py clearsessions` manually.

To use **local PostgreSQL**, create a database and user in your PostgreSQL installation, set `DB_ENGINE=postgresql`, fill in `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`, and use `DB_HOST=127.0.0.1`. Then run the same migration/startup commands below. Database contents are not transferred when switching engines. Redis remains independently optional.

## Docker setup

Docker support is retained. Configure nonempty PostgreSQL credentials in `.env` first. Compose explicitly overrides the local database/cache/task choices with PostgreSQL, the `db`/`redis` service names, and asynchronous Celery tasks. Database and Redis host ports bind to loopback only.

```powershell
docker compose build
docker compose up -d db redis
docker compose logs db redis
```

Wait until PostgreSQL and Redis are ready, then:

```powershell
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose up web celery_worker celery_beat
```

The PostgreSQL named volume retains data. Do not change credentials for an existing volume without updating the corresponding PostgreSQL role. `.dockerignore` excludes local secrets, databases, generated files, and uploads from the build context while retaining `pictures/default.png`. The development bind mount still intentionally exposes local project files to running containers.

## Database migrations

For the local setup:

```powershell
python manage.py migrate
python manage.py migrate --check
```

Migrations are supplied for both apps. Startup does not apply them automatically. A fresh database has no course content or accounts; no seed fixtures are provided.

## Creating a superuser

```powershell
python manage.py createsuperuser
```

Use [Django admin](http://127.0.0.1:8000/admin/) to create courses and lessons, manage author permissions, and set free/full account types.

## Running the project

With your virtual environment activated and `.env` configured:

```powershell
python manage.py check
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Stop the server with Ctrl+C. Uploaded media stays in `pictures/`. Existing media and the legacy database are not deleted by the local setup.

For Docker, stop services with `docker compose down`; this retains the PostgreSQL volume.

## Tests and CI

Tests are implemented in [`courses/tests.py`](courses/tests.py), [`users/tests.py`](users/tests.py), and [`tests/test_regressions.py`](tests/test_regressions.py), using pytest and pytest-django. pytest-cov provides coverage reporting. Tests exercise page responses, lesson access, comments, profiles, model helpers, and background-task functions.

For local SQLite/local-memory mode:

```powershell
python -m pytest --cov=. --cov-report=term
```

For PostgreSQL/Redis integration testing with Compose:

```powershell
docker compose run --rm web pytest --cov=. --cov-report=term
```

Tests use the selected database backend and cache; some clear the configured cache. Use a dedicated development/test environment. The local suite passing does not verify PostgreSQL or Redis integration.

The [GitHub Actions test workflow](.github/workflows/tests.yml) runs on pushes and pull requests targeting `main` or `master`. It prepares `.env` from the example with temporary generated credentials, builds the web image, starts PostgreSQL and Redis, and runs tests with terminal coverage output.

The separate [manual test-deployment workflow](.github/workflows/deploy-test.yml) starts Docker Compose on a GitHub-hosted runner. It does not provide a persistent public deployment. The Windows local configuration was validated with Django checks, migrations, the original tests, and HTTP requests to the development server. The application review subsequently passed 35 tests, with one PostgreSQL-only concurrency test skipped on SQLite. Docker and live PostgreSQL/Redis integration were not run during this pass.

## Current limitations

- The email backend currently prints messages to the console; real email delivery is not configured.
- The pricing/purchase UI does not include real payment integration. Full-account access is managed through profile data.
- The Docker and deployment setup is development-oriented: it uses Django's development server, local bind mounts, and development configuration.
- Password reset is covered end to end by regression tests, including expired and reused tokens. Development emails still print to the console.
- Course announcements respect active-user email consent and send separate messages after commit. Dispatch failures are logged, but there is no durable retry/outbox mechanism yet.
- Local-memory counters and rate limits are development-only, and eager tasks execute synchronously.
- The old database, IDE files, and bytecode have been removed from Git tracking while preserving local copies. They still exist in previous commits.
- A historical Django secret key is compromised. The local `.env` key was replaced; any other environment using the old key must also replace it, without keeping that key in `SECRET_KEY_FALLBACKS`. Rotation invalidates existing signed sessions/tokens. Before publication, separately review historical database/account data and remove sensitive paths/keys from all affected Git history using a coordinated history rewrite. No history rewrite has been performed.

## Author / Contact

Author and public contact details will be added by the repository owner.

<!-- Replace this placeholder with your preferred public name, GitHub profile,
and optional LinkedIn profile or contact email. -->
