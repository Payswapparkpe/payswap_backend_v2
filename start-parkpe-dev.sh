#!/bin/bash
# ParkPe local dev: run Django + ParkPe in two terminals.
# Terminal 1: ./start-parkpe-dev.sh backend
# Terminal 2: ./start-parkpe-dev.sh frontend

set -e
cd "$(dirname "$0")"

case "${1:-}" in
  backend)
    echo "Starting Django on http://0.0.0.0:8000 (LAN: http://<your-IP>:8000) ..."
    source .venv/bin/activate
    cd backend
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  frontend)
    echo "Starting ParkPe on http://0.0.0.0:4201 (LAN: http://<your-IP>:4201) ..."
    cd frontend
    exec npm run start -- --project=parkpe --host 0.0.0.0
    ;;
  *)
    echo "Usage: $0 backend   # run in Terminal 1 (listens on 0.0.0.0:8000)"
    echo "       $0 frontend  # run in Terminal 2 (listens on 0.0.0.0:4201)"
    echo ""
    echo "Open from this machine: http://localhost:4201"
    echo "Open from LAN (phone/tablet): http://<this-machine-IP>:4201"
    exit 1
    ;;
esac
