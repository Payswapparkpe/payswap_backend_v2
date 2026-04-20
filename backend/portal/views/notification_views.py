from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from portal.models import (
    NotificationAudienceRule,
    NotificationBanner,
    NotificationCampaign,
    NotificationDeliveryLog,
    NotificationEventRule,
    NotificationMessageTemplate,
    UserNotification,
)
from portal.services.notification_orchestrator import NotificationOrchestrator


def _is_notifications_admin(user):
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser or user.is_staff or getattr(user, "role_code", "").lower() in ("super_admin", "admin"))


def _parse_dt(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class NotificationCenterView(TemplateView):
    template_name = "portal/notifications/manage.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_notifications_admin(request.user):
            messages.error(request, "Access denied. Admin role required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = str(self.request.GET.get("tab") or "campaigns").strip().lower()
        platform = str(self.request.GET.get("platform") or "").strip().lower()
        slot = str(self.request.GET.get("slot") or "").strip().lower()
        q = NotificationBanner.objects.all().order_by("priority", "-created_at")
        if platform:
            q = q.filter(platform=platform)
        if slot:
            q = q.filter(slot=slot)
        ctx["banners"] = q
        ctx["platform_filter"] = platform
        ctx["slot_filter"] = slot
        ctx["slot_choices"] = NotificationBanner.SLOT_CHOICES
        ctx["platform_choices"] = NotificationBanner.PLATFORM_CHOICES
        ctx["active_tab"] = tab
        ctx["campaigns"] = NotificationCampaign.objects.order_by("-created_at")[:120]
        ctx["templates"] = NotificationMessageTemplate.objects.select_related("campaign").order_by("-updated_at")[:200]
        ctx["delivery_logs"] = NotificationDeliveryLog.objects.select_related("campaign", "user").order_by("-created_at")[:250]
        ctx["inbox_items"] = UserNotification.objects.select_related("user", "campaign").order_by("-created_at")[:200]
        ctx["campaign_status_choices"] = NotificationCampaign.STATUS_CHOICES
        ctx["campaign_type_choices"] = NotificationCampaign.TYPE_CHOICES
        ctx["channel_choices"] = NotificationMessageTemplate.CHANNEL_CHOICES
        ctx["delivery_stats"] = (
            NotificationDeliveryLog.objects.values("status").annotate(total=Count("id")).order_by("status")
        )
        ctx["unread_total"] = UserNotification.objects.filter(is_read=False).count()
        return ctx


@require_POST
@login_required
def notification_banner_create_view(request):
    if not _is_notifications_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)

    title = str(request.POST.get("title") or "").strip()
    message_text = str(request.POST.get("message") or "").strip()
    slot = str(request.POST.get("slot") or NotificationBanner.SLOT_BBPS_RIGHT_RAIL).strip()
    platform = str(request.POST.get("platform") or NotificationBanner.PLATFORM_BOTH).strip()
    if not title or not message_text:
        messages.error(request, "Title and message are required.")
        return redirect("/notifications/")

    name = str(request.POST.get("name") or title).strip()[:120]
    service_code = str(request.POST.get("service_code") or "").strip().lower()
    screen_code = str(request.POST.get("screen_code") or "").strip().lower()
    cta_text = str(request.POST.get("cta_text") or "").strip()[:48]
    cta_url = str(request.POST.get("cta_url") or "").strip()[:255]
    image_url = str(request.POST.get("image_url") or "").strip()[:255]
    bg_color = str(request.POST.get("bg_color") or "#1f4f94").strip()[:16]
    text_color = str(request.POST.get("text_color") or "#ffffff").strip()[:16]
    starts_at = _parse_dt(request.POST.get("starts_at"))
    ends_at = _parse_dt(request.POST.get("ends_at"))
    try:
        priority = int(request.POST.get("priority") or 100)
    except ValueError:
        priority = 100

    campaign_id = request.POST.get("campaign_id")
    campaign = None
    if campaign_id:
        campaign = NotificationCampaign.objects.filter(id=campaign_id).first()

    NotificationBanner.objects.create(
        name=name,
        title=title,
        message=message_text,
        cta_text=cta_text,
        cta_url=cta_url,
        image_url=image_url,
        bg_color=bg_color,
        text_color=text_color,
        slot=slot,
        platform=platform,
        service_code=service_code,
        screen_code=screen_code,
        starts_at=starts_at,
        ends_at=ends_at,
        campaign=campaign,
        priority=priority,
        created_by=request.user,
    )
    messages.success(request, "Notification banner created.")
    return redirect("/notifications/")


@require_POST
@login_required
def notification_banner_toggle_view(request, banner_id):
    if not _is_notifications_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)
    banner = get_object_or_404(NotificationBanner, id=banner_id)
    enabled = str(request.POST.get("enabled") or "").strip().lower() in ("1", "true", "on", "yes")
    banner.is_active = enabled
    banner.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"success": True, "is_active": banner.is_active})


@require_POST
@login_required
def notification_banner_delete_view(request, banner_id):
    if not _is_notifications_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)
    banner = get_object_or_404(NotificationBanner, id=banner_id)
    banner.delete()
    return JsonResponse({"success": True})


@require_POST
@login_required
def notification_campaign_create_view(request):
    if not _is_notifications_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)

    name = str(request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Campaign name is required.")
        return redirect("/notifications/?tab=campaigns")

    campaign_type = str(request.POST.get("campaign_type") or NotificationCampaign.TYPE_MANUAL).strip().lower()
    event_key = str(request.POST.get("event_key") or "").strip().lower()
    channels = [x.strip().lower() for x in str(request.POST.get("channels") or "").split(",") if x.strip()]
    starts_at = _parse_dt(request.POST.get("starts_at"))
    ends_at = _parse_dt(request.POST.get("ends_at"))
    status = str(request.POST.get("status") or NotificationCampaign.STATUS_DRAFT).strip().lower()
    try:
        campaign_priority = int(request.POST.get("priority") or 100)
    except ValueError:
        campaign_priority = 100
    payload = {
        "slot": str(request.POST.get("slot") or NotificationBanner.SLOT_SERVICE_INLINE).strip(),
        "platform": str(request.POST.get("platform") or NotificationBanner.PLATFORM_BOTH).strip(),
        "service_code": str(request.POST.get("service_code") or "").strip().lower(),
        "screen_code": str(request.POST.get("screen_code") or "").strip().lower(),
        "priority": campaign_priority,
    }

    campaign = NotificationCampaign.objects.create(
        name=name[:140],
        campaign_type=campaign_type,
        event_key=event_key[:80],
        description=str(request.POST.get("description") or "").strip()[:320],
        channels=channels,
        payload=payload,
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
        created_by=request.user,
    )

    NotificationAudienceRule.objects.create(
        campaign=campaign,
        platform=str(request.POST.get("audience_platform") or NotificationBanner.PLATFORM_BOTH).strip().lower(),
        service_code=str(request.POST.get("audience_service_code") or "").strip().lower(),
        screen_code=str(request.POST.get("audience_screen_code") or "").strip().lower(),
        role_code=str(request.POST.get("audience_role_code") or "").strip(),
        user_ids=[int(x) for x in str(request.POST.get("audience_user_ids") or "").replace(" ", "").split(",") if x.isdigit()],
    )
    if campaign_type == NotificationCampaign.TYPE_EVENT and event_key:
        NotificationEventRule.objects.create(
            campaign=campaign,
            event_key=event_key,
            condition_json={},
        )

    NotificationMessageTemplate.objects.update_or_create(
        campaign=campaign,
        channel=NotificationMessageTemplate.CHANNEL_IN_APP,
        defaults={
            "title": str(request.POST.get("in_app_title") or campaign.name).strip()[:160],
            "body": str(request.POST.get("in_app_body") or "").strip(),
            "cta_text": str(request.POST.get("in_app_cta_text") or "").strip()[:64],
            "cta_url": str(request.POST.get("in_app_cta_url") or "").strip()[:255],
        },
    )
    NotificationMessageTemplate.objects.update_or_create(
        campaign=campaign,
        channel=NotificationMessageTemplate.CHANNEL_EMAIL,
        defaults={
            "subject": str(request.POST.get("email_subject") or campaign.name).strip()[:160],
            "title": str(request.POST.get("email_title") or campaign.name).strip()[:160],
            "body": str(request.POST.get("email_body") or "").strip(),
        },
    )
    NotificationMessageTemplate.objects.update_or_create(
        campaign=campaign,
        channel=NotificationMessageTemplate.CHANNEL_SMS,
        defaults={
            "title": "SMS",
            "body": str(request.POST.get("sms_body") or "").strip(),
        },
    )
    NotificationMessageTemplate.objects.update_or_create(
        campaign=campaign,
        channel=NotificationMessageTemplate.CHANNEL_PUSH,
        defaults={
            "title": str(request.POST.get("push_title") or campaign.name).strip()[:160],
            "body": str(request.POST.get("push_body") or "").strip(),
            "cta_url": str(request.POST.get("push_cta_url") or "").strip()[:255],
        },
    )
    NotificationMessageTemplate.objects.update_or_create(
        campaign=campaign,
        channel=NotificationMessageTemplate.CHANNEL_BANNER,
        defaults={
            "title": str(request.POST.get("banner_title") or campaign.name).strip()[:160],
            "body": str(request.POST.get("banner_body") or "").strip(),
            "cta_text": str(request.POST.get("banner_cta_text") or "").strip()[:64],
            "cta_url": str(request.POST.get("banner_cta_url") or "").strip()[:255],
            "image_url": str(request.POST.get("banner_image_url") or "").strip()[:255],
        },
    )

    messages.success(request, "Campaign created.")
    return redirect("/notifications/?tab=campaigns")


@require_POST
@login_required
def notification_campaign_toggle_view(request, campaign_id):
    if not _is_notifications_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)
    campaign = get_object_or_404(NotificationCampaign, id=campaign_id)
    to_status = str(request.POST.get("status") or "").strip().lower()
    if to_status not in dict(NotificationCampaign.STATUS_CHOICES):
        to_status = NotificationCampaign.STATUS_PAUSED if campaign.status == NotificationCampaign.STATUS_RUNNING else NotificationCampaign.STATUS_RUNNING
    campaign.status = to_status
    campaign.save(update_fields=["status", "updated_at"])
    return JsonResponse({"success": True, "status": campaign.status})


@require_POST
@login_required
def notification_campaign_duplicate_view(request, campaign_id):
    if not _is_notifications_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)
    src = get_object_or_404(NotificationCampaign, id=campaign_id)
    copy = NotificationCampaign.objects.create(
        name=f"{src.name} (Copy)"[:140],
        campaign_type=src.campaign_type,
        event_key=src.event_key,
        description=src.description,
        channels=src.channels,
        payload=src.payload,
        status=NotificationCampaign.STATUS_DRAFT,
        starts_at=src.starts_at,
        ends_at=src.ends_at,
        created_by=request.user,
    )
    for row in src.audience_rules.all():
        NotificationAudienceRule.objects.create(
            campaign=copy,
            platform=row.platform,
            service_code=row.service_code,
            screen_code=row.screen_code,
            role_code=row.role_code,
            user_ids=row.user_ids,
            filters=row.filters,
        )
    for row in src.templates.all():
        NotificationMessageTemplate.objects.create(
            campaign=copy,
            channel=row.channel,
            subject=row.subject,
            title=row.title,
            body=row.body,
            cta_text=row.cta_text,
            cta_url=row.cta_url,
            image_url=row.image_url,
            metadata=row.metadata,
        )
    messages.success(request, "Campaign duplicated.")
    return redirect("/notifications/?tab=campaigns")


@require_POST
@login_required
def notification_campaign_send_now_view(request, campaign_id):
    if not _is_notifications_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect("/notifications/?tab=campaigns")
    campaign = get_object_or_404(NotificationCampaign, id=campaign_id)
    campaign.status = NotificationCampaign.STATUS_RUNNING
    campaign.starts_at = campaign.starts_at or timezone.now()
    campaign.save(update_fields=["status", "starts_at", "updated_at"])
    result = NotificationOrchestrator().dispatch_campaign(campaign, actor_id=request.user.id)

    if result.get("reason") == "no_audience":
        messages.warning(
            request,
            f"Campaign “{campaign.name}”: no users matched the audience rules — nothing was sent.",
        )
    else:
        ch = ", ".join(result.get("channels") or [])
        messages.success(
            request,
            f"Campaign “{campaign.name}” dispatched: {result.get('sent', 0)} delivery attempts "
            f"across [{ch}] for {result.get('users', 0)} user(s).",
        )
    return redirect("/notifications/?tab=campaigns")


@login_required
def notification_campaign_audience_preview_view(request, campaign_id):
    if not _is_notifications_admin(request.user):
        if request.GET.get("format") == "json":
            return JsonResponse({"success": False, "message": "Access denied."}, status=403)
        messages.error(request, "Access denied.")
        return redirect("/notifications/?tab=campaigns")
    campaign = get_object_or_404(NotificationCampaign, id=campaign_id)
    orchestrator = NotificationOrchestrator()
    all_users = orchestrator._resolve_audience(campaign)  # noqa: SLF001
    total = len(all_users)
    preview_limit = 100
    sample_users = all_users[:preview_limit]
    audience_rows = [
        {
            "id": u.id,
            "username": getattr(u, "username", ""),
            "email_display": (getattr(u, "email", "") or "").strip() or "—",
        }
        for u in sample_users
    ]

    if request.GET.get("format") == "json":
        sample_json = [
            {
                "id": u.id,
                "username": getattr(u, "username", ""),
                "email": getattr(u, "email", "") or None,
            }
            for u in sample_users
        ]
        return JsonResponse({"success": True, "count": total, "sample": sample_json})

    return render(
        request,
        "portal/notifications/campaign_audience_preview.html",
        {
            "campaign": campaign,
            "audience_total": total,
            "audience_rows": audience_rows,
            "preview_limit": preview_limit,
            "truncated": total > preview_limit,
        },
    )


@login_required
def notification_analytics_view(request):
    if not _is_notifications_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)
    stats = (
        NotificationDeliveryLog.objects.values("channel", "status").annotate(total=Count("id")).order_by("channel", "status")
    )
    unread = UserNotification.objects.filter(is_read=False).count()
    total_inbox = UserNotification.objects.count()
    return JsonResponse({"success": True, "stats": list(stats), "unread": unread, "inbox_total": total_inbox})
