# Scripts

One-off or utility scripts. Prefer **management commands** (`python manage.py <command>`) when the task needs Django (DB, settings, models).

| Script | Purpose |
|--------|--------|
| `send_parkpe_test_email.py` | Send a test email (ParkPe). Prefer: `python manage.py send_parkpe_test_email <email>` from project root. |
| `fetch_carwale_images.py` | Fetch CarWale images into `Image Files/car image/`. Run from project root. |

Run from **project root**, e.g.:

```bash
python scripts/fetch_carwale_images.py
```
