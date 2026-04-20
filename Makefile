# Quick dev servers (run each target in its own terminal).
# ParkPe Angular: http://localhost:4201  |  Django hub: http://localhost:8000

.PHONY: help parkpe hub parkpe-app

help:
	@echo "make parkpe     — ParkPe Angular app (frontend/, port 4201)"
	@echo "make hub        — Payswap Django backend (backend/manage.py, port 8000)"
	@echo "make parkpe-app — ParkPe Flutter app (parkpe_app/); optional DEVICE=chrome|macos|..."

parkpe:
	cd frontend && npm run start -- --project=parkpe --host 0.0.0.0

hub:
	@if [ -f .venv/bin/activate ]; then \
		. .venv/bin/activate && cd backend && exec python manage.py runserver 0.0.0.0:8000; \
	else \
		cd backend && exec python3 manage.py runserver 0.0.0.0:8000; \
	fi

# Flutter: cd parkpe_app, deps, then run.
# On macOS, DEVICE defaults to `macos` so the command is non-interactive (`flutter run` otherwise prompts).
# Override: make parkpe-app DEVICE=chrome   or   DEVICE=android
ifneq ($(DEVICE),)
PARKPE_RUN_DEVICE := $(DEVICE)
else
ifeq ($(shell uname -s),Darwin)
PARKPE_RUN_DEVICE := macos
else
PARKPE_RUN_DEVICE :=
endif
endif

parkpe-app:
	cd parkpe_app && flutter pub get && \
	if [ -n "$(PARKPE_RUN_DEVICE)" ]; then flutter run -d "$(PARKPE_RUN_DEVICE)"; else flutter run; fi
