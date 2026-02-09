"""
Resend pending/failed emails from EmailQueue. Works without Celery.
Safe to run multiple times; idempotent per EmailQueue row.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.models import EmailQueue
from portal.services.email_queue_service import send_email_from_queue_row

logger = logging.getLogger('portal.email')


class Command(BaseCommand):
    help = 'Resend emails with status PENDING or FAILED. Does not require Celery.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='Max number of rows to process (default: 500)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be sent, do not send',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']

        qs = EmailQueue.objects.filter(
            status__in=[EmailQueue.STATUS_PENDING, EmailQueue.STATUS_FAILED]
        ).order_by('created_at')[:limit]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No pending or failed emails.'))
            return

        self.stdout.write(f'Found {total} row(s) to process.' + (' (dry-run)' if dry_run else ''))

        sent = 0
        failed = 0
        for row in qs:
            if dry_run:
                self.stdout.write(f'  Would send: id={row.id} to={row.to_email[:16]}... subject={row.subject[:40]}...')
                sent += 1
                continue
            success, err = send_email_from_queue_row(row)
            if success:
                row.status = EmailQueue.STATUS_SENT
                row.sent_at = timezone.now()
                row.save(update_fields=['status', 'sent_at'])
                sent += 1
                logger.info('resend_pending_emails: sent', extra={'action': 'resend_sent', 'queue_id': row.id})
            else:
                row.retry_count = (row.retry_count or 0) + 1
                row.last_error = (err or '')[:2000]
                row.save(update_fields=['retry_count', 'last_error'])
                failed += 1
                logger.warning(
                    'resend_pending_emails: failed',
                    extra={'action': 'resend_failed', 'queue_id': row.id, 'error': (err or '')[:200]},
                )

        self.stdout.write(self.style.SUCCESS(f'Sent: {sent}, Failed: {failed}'))
