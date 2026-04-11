# Payswap monorepo layout

Top level is organized by **stack**, not mixed together.

## Layout

| Directory | Contents |
|-----------|----------|
| **`backend/`** | Django: `manage.py`, `core/`, `api/`, `portal/`, `rbac/`, tests, static/media roots, `requirements.txt`, vendor reference folders (`Cashfree/`, `Mobikwik/`, `DLT/`). |
| **`frontend/`** | Angular workspace: `angular.json`, `projects/parkpe`, `projects/payswap`, `projects/shared`, etc. |
| **`docs/`** | Project documentation. |
| **`deploy/`** | Systemd units and deployment notes (`WorkingDirectory` → `…/backend`). |
| **`scripts/`** | Helper scripts; many run commands under `backend/`. |
| **`parkpe_app/`** | Flutter app (native ParkPe). |
| **`app ui/`** | Separate Flutter project (space in name is legacy). |

## Root files

- **`.env`** — Usually at repo root; `backend/core/config.py` resolves `../.env` then `backend/.env`.
- **`Procfile`** — Web/worker/beat; each process `cd backend` then runs gunicorn/celery.
- **`Makefile`** — `make hub` → Django, `make parkpe` → Angular.

## Conventions

- Run **`python manage.py`** only after **`cd backend`** (or use `make hub`).
- Run **`npm` / `ng`** from **`frontend/`**.
- CI (`.github/workflows/ci.yml`) uses `working-directory: backend` and `working-directory: frontend`.
