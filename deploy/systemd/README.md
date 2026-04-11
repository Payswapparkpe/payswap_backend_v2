# Celery systemd services (Payswap / ParkPe)

Celery must auto-start and auto-restart so email delivery never depends on manual start.

## Install

1. Copy service files (edit `WorkingDirectory` and `ExecStart` paths if your app lives elsewhere):

   ```bash
   sudo cp deploy/systemd/celery-worker.service /etc/systemd/system/
   sudo cp deploy/systemd/celery-beat.service /etc/systemd/system/
   ```

2. If your app is not at `/var/www/payswap` with Django under `backend/` and a venv at `/var/www/payswap/venv`, edit both files:

   - `WorkingDirectory=/path/to/payswap/backend`
   - `ExecStart=/path/to/payswap/venv/bin/celery -A core worker -l info` (and beat equivalent)
   - Optionally set `User=` and `Group=` to your app user.

3. Enable and start:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable celery-worker
   sudo systemctl start celery-worker
   # If using periodic tasks:
   sudo systemctl enable celery-beat
   sudo systemctl start celery-beat
   ```

## Behaviour

- **Restart=always** – process is restarted if it exits (crash, OOM, etc.).
- **RestartSec=10** – wait 10 seconds before restart.
- **WantedBy=multi-user.target** – start on boot.
- Logs go to **journald**: `journalctl -u celery-worker -f`, `journalctl -u celery-beat -f`.

## Fallback (no Celery)

If Celery is down, pending emails are not lost. Run:

```bash
cd /path/to/payswap/backend && python manage.py resend_pending_emails
```

This works without Celery and is safe to run multiple times (e.g. from cron).
