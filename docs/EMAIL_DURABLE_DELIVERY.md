# Email Delivery – Durable and Survives Celery Failure

**Email delivery is durable and survives Celery failure.**

- **Source of truth:** All outbound emails (e.g. voucher delivery) are written to the **EmailQueue** table before any send. No email is sent directly from the request/transaction.
- **Celery:** A worker task (`process_email_queue`) reads from EmailQueue by ID, sends via SMTP, and marks the row SENT or FAILED. The task uses `acks_late=True`, `reject_on_worker_lost=True`, autoretry with backoff, and `max_retries=5` so that worker crashes and transient failures do not lose emails.
- **Fallback:** If Celery is down or a task never runs, pending emails are recovered by the Django management command **`python manage.py resend_pending_emails`**. It runs without Celery, is safe to run multiple times, and is idempotent per EmailQueue row.
- **Supervision:** Celery worker (and beat, if used) are supervised by **systemd** with `Restart=always`, `RestartSec=10`, and start on boot so Celery auto-starts and auto-restarts.
- **Logging:** Email enqueue, send success, send failure, and retries are logged to the **file system** (e.g. `logs/email.log`). No email content or secrets are logged.

Duplicate emails are acceptable; lost emails are not.

## Cron (optional)

To retry pending emails even when Celery is down, run the fallback command periodically, e.g. every 15 minutes:

```bash
*/15 * * * * cd /var/www/payswap && /var/www/payswap/venv/bin/python manage.py resend_pending_emails --limit 200
```

Adjust paths and `--limit` as needed.
