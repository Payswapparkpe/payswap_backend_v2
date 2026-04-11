# Payswap backend (Django)

This directory is the Django project root: `manage.py`, apps (`core`, `api`, `portal`, `rbac`), `requirements.txt`, and `pytest.ini`.

- **Run server:** `python manage.py runserver` (from this directory, with venv activated).
- **Environment:** Prefer a `.env` file at the **repository root** (parent folder); `core/config.py` loads that first, then `backend/.env` if present.
- **Vendor assets:** `Cashfree/`, `Mobikwik/`, `DLT/` live here; paths in `.env` are usually relative to this directory when you run `manage.py` from here.

See the repo root `README.md` and `PROJECT_STRUCTURE.md` for the full monorepo layout.
