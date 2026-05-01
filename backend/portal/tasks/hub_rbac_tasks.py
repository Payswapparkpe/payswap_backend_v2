"""
Hub RBAC background tasks.
- expire_hub_assignments: Deactivate UserHubAssignments whose expires_at has passed.
  Run periodically via Celery Beat (e.g. every hour).
"""
from celery import shared_task
from django.utils import timezone
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.tasks.hub_rbac")


@shared_task(name="hub_rbac.expire_hub_assignments", bind=True, max_retries=3)
def expire_hub_assignments(self):
    """
    Scan UserHubAssignment rows where expires_at is in the past and is_active=True.
    Sets is_active=False and logs the deactivation for audit.
    """
    try:
        from rbac.models import UserHubAssignment
        from portal.models import LogEntry

        now = timezone.now()
        expired = UserHubAssignment.objects.filter(
            is_active=True,
            expires_at__lte=now,
        ).select_related("user", "department", "project")

        count = 0
        for assignment in expired:
            assignment.is_active = False
            assignment.save(update_fields=["is_active"])
            try:
                LogEntry.objects.create(
                    log_level="INFO",
                    category="security",
                    message=f"Hub assignment auto-expired",
                    module_name="portal.tasks.hub_rbac",
                    extra_data={
                        "action": "assignment.auto_expire",
                        "assignment_id": assignment.id,
                        "user_id": assignment.user_id,
                        "department": assignment.department.code,
                        "project": assignment.project.code,
                        "expires_at": str(assignment.expires_at),
                    },
                )
            except Exception:
                pass
            count += 1

        logger.info(
            f"expire_hub_assignments: deactivated {count} expired assignments",
            extra_data={"count": count},
        )
        return {"expired_count": count}
    except Exception as exc:
        logger.error(f"expire_hub_assignments failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)
