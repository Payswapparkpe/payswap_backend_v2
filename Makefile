# Quick dev servers (run each target in its own terminal).
# ParkPe Angular: http://localhost:4201  |  Django hub: http://localhost:8000

.PHONY: help parkpe hub

help:
	@echo "make parkpe  — ParkPe Angular app (frontend/, port 4201)"
	@echo "make hub     — Payswap Django backend (backend/manage.py, port 8000)"

parkpe:
	cd frontend && npm run start -- --project=parkpe --host 0.0.0.0

hub:
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && cd backend && exec python manage.py runserver 0.0.0.0:8000; \
	else \
		cd backend && exec python3 manage.py runserver 0.0.0.0:8000; \
	fi
