# Django Academy — Online Learning Platform

## Overview

Django Academy is a server-rendered Django learning platform with a course catalog, embedded YouTube lessons, user accounts and profiles, and lesson discussions. Authors and superusers can create courses, with permissions controlling access to protected actions.

## Features

- Course catalog and detail pages with ordered lessons and embedded YouTube videos.
- Registration, login, logout, and password reset.
- User profiles with avatars.
- Course creation for authors and superusers.
- Authenticated comments, pagination, and a per-user comment cooldown.
- Redis-backed course view counters and request throttling.
- Background course-announcement emails through Celery.
- Scheduled expired-session cleanup through Celery Beat.
- Django admin for managing application content and users.

## Tech Stack

| Area | Technologies |
| --- | --- |
| Backend | Python, Django |
| Database and cache | PostgreSQL, Redis |
| Background tasks | Celery, Celery Beat |
| Frontend | Django templates, Bootstrap |
| Development environment | Docker, Docker Compose |
| Testing and CI | pytest, GitHub Actions |

SQLite and local-memory caching are also supported for local development. Python dependencies are listed in [requirements.txt](requirements.txt).

## Screenshots

Screenshots are planned for the course catalog, course details, lesson comments, and user profile.

<!-- Uncomment each image when its file has been added. -->
<!-- ![Course catalog](docs/images/course-catalog.png) -->
<!-- ![Course details](docs/images/course-detail.png) -->
<!-- ![Lesson and comments](docs/images/lesson-comments.png) -->
<!-- ![User profile](docs/images/user-profile.png) -->

## Project Structure

```text
DjangoStore/          # Settings, URLs, middleware, and Celery configuration
courses/              # Courses, lessons, comments, and announcement tasks
users/                # Registration, profiles, and authentication
templates/           # Server-rendered pages
static/               # Application styles
pictures/             # Default avatar and uploaded media
tests/                # Regression and service integration tests
manage.py             # Django management commands
requirements.txt      # Python dependencies
docker-compose.yml    # Development services
```

## Running Locally

Run these PowerShell commands from the repository root. Create `.venv` if needed, activate it, and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For a new checkout, copy the example configuration to `.env` and generate a secret key. Keep an existing `.env` instead of overwriting it.

```powershell
Copy-Item .env.example .env
python -c "from pathlib import Path; import secrets; p=Path('.env'); p.write_text(p.read_text().replace('replace-with-a-generated-secret-key', secrets.token_urlsafe(64)))"
```

The example enables `DEBUG=True`, SQLite, local-memory caching, and eager Celery tasks. This mode runs without PostgreSQL, Redis, or a Celery worker; tasks execute synchronously, and counters are local to the server process. Local emails appear in the console. Scheduled cleanup requires a worker and Beat; locally, it can be run manually with `python manage.py clearsessions`.

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open [localhost:8000](http://127.0.0.1:8000/). Use [Django admin](http://127.0.0.1:8000/admin/) to add courses and lessons and manage author permissions. A fresh database starts without course content.

## Docker

Docker Compose supports PostgreSQL, Redis, Django, a Celery worker, and Celery Beat. Configure `.env` as above and set `POSTGRES_DB`, `POSTGRES_USER`, and a nonempty `POSTGRES_PASSWORD`. Compose selects PostgreSQL, Redis, and asynchronous task execution.

```powershell
docker compose build
docker compose up -d db redis
```

Once PostgreSQL and Redis are ready:

```powershell
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose up web celery_worker celery_beat
```

This is a development environment. Stop services with `docker compose down`; the PostgreSQL volume is retained.

## Tests

The pytest suite covers application behavior, regression cases, and PostgreSQL/Redis integration. With the local environment configured:

```powershell
python manage.py check
python -m pytest
```

- Latest local validation: **35 passed, 4 expected skips** for tests requiring PostgreSQL or Redis; Django system checks passed.
- Latest verified PostgreSQL + Redis integration result: **39 passed, 0 failed, 0 skipped**.

See [integration testing instructions](docs/integration-testing.md) for the dedicated service setup and opt-in tests. [GitHub Actions](.github/workflows/tests.yml) provides automated testing.

## Current Limitations

- Deployment is development-oriented and uses Django's development server.
- Local email uses the console backend.
- No real payment integration; account access is managed through profile data.
- Durable notification retries and an outbox are not implemented.

