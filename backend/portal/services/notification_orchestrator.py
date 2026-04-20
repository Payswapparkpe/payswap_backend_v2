from __future__ import annotations

from dataclasses import dataclass
from datetime import time, timedelta
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import QuerySet
from django.utils import timezone

from portal.models import (
    DevicePushToken,
    NotificationAudienceRule,
    NotificationBanner,
    NotificationCampaign,
    NotificationDeliveryLog,
    NotificationEventRule,
    NotificationMessageTemplate,
    Profile,
    UserNotification,
)
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.notifications.orchestrator")
User = get_user_model()


@dataclass
class DispatchResult:
    channel: str
    status: str
    destination: str = ""
    provider_message_id: str = ""
    response: dict | None = None
    error_message: str = ""


class NotificationOrchestrator:
    DEFAULT_CHANNELS = [
        NotificationMessageTemplate.CHANNEL_IN_APP,
        NotificationMessageTemplate.CHANNEL_PUSH,
        NotificationMessageTemplate.CHANNEL_SMS,
        NotificationMessageTemplate.CHANNEL_EMAIL,
        NotificationMessageTemplate.CHANNEL_BANNER,
    ]

    def dispatch_campaign(
        self,
        campaign: NotificationCampaign,
        *,
        actor_id: Optional[int] = None,
        event_payload: Optional[dict] = None,
    ) -> dict:
        users = self._resolve_audience(campaign)
        templates = {
            t.channel: t
            for t in campaign.templates.all()
        }
        channels = self._resolve_channels(campaign)
        now = timezone.now()
        if not users:
            return {"sent": 0, "reason": "no_audience"}

        sent = 0
        for user in users:
            if not self._is_rollout_enabled(user):
                self._log(
                    campaign=campaign,
                    user=user,
                    channel="system",
                    status=NotificationDeliveryLog.STATUS_FAILED,
                    error_message="rollout_filtered",
                    request_payload={"actor_id": actor_id, "event_payload": event_payload or {}},
                )
                continue
            if self._is_rate_limited(user):
                self._log(
                    campaign=campaign,
                    user=user,
                    channel="system",
                    status=NotificationDeliveryLog.STATUS_FAILED,
                    error_message="rate_limited",
                    request_payload={"actor_id": actor_id, "event_payload": event_payload or {}},
                )
                continue
            if self._is_quiet_hour(campaign, now):
                self._log(
                    campaign=campaign,
                    user=user,
                    channel="system",
                    status=NotificationDeliveryLog.STATUS_FAILED,
                    error_message="quiet_hours",
                    request_payload={"actor_id": actor_id, "event_payload": event_payload or {}},
                )
                continue

            for channel in channels:
                template = templates.get(channel)
                if not template and channel != NotificationMessageTemplate.CHANNEL_BANNER:
                    continue
                result = self._dispatch_single_channel(
                    campaign=campaign,
                    user=user,
                    channel=channel,
                    template=template,
                    event_payload=event_payload or {},
                )
                self._log_result(campaign, user, channel, result, actor_id, event_payload)
                if result.status in (
                    NotificationDeliveryLog.STATUS_SENT,
                    NotificationDeliveryLog.STATUS_DELIVERED,
                ):
                    sent += 1

        if campaign.status in (NotificationCampaign.STATUS_DRAFT, NotificationCampaign.STATUS_SCHEDULED):
            campaign.status = NotificationCampaign.STATUS_RUNNING
        campaign.updated_at = timezone.now()
        campaign.save(update_fields=["status", "updated_at"])
        return {"sent": sent, "users": len(users), "channels": channels}

    def dispatch_event(
        self,
        event_key: str,
        *,
        event_payload: Optional[dict] = None,
        actor_id: Optional[int] = None,
    ) -> int:
        now = timezone.now()
        count = 0
        event_key = event_key.strip().lower()
        rule_qs = NotificationEventRule.objects.filter(
            event_key=event_key,
            is_active=True,
            campaign__campaign_type=NotificationCampaign.TYPE_EVENT,
            campaign__status__in=[
                NotificationCampaign.STATUS_RUNNING,
                NotificationCampaign.STATUS_SCHEDULED,
                NotificationCampaign.STATUS_DRAFT,
            ],
        ).filter(
            models.Q(campaign__starts_at__isnull=True) | models.Q(campaign__starts_at__lte=now),
            models.Q(campaign__ends_at__isnull=True) | models.Q(campaign__ends_at__gte=now),
        ).select_related("campaign")
        for rule in rule_qs:
            if not self._event_matches(rule, event_payload or {}):
                continue
            campaign = rule.campaign
            out = self.dispatch_campaign(campaign, actor_id=actor_id, event_payload=event_payload or {})
            count += int(out.get("sent") or 0)
        return count

    def _event_matches(self, rule: NotificationEventRule, event_payload: dict) -> bool:
        cond = rule.condition_json if isinstance(rule.condition_json, dict) else {}
        for key, expected in cond.items():
            if key not in event_payload:
                return False
            if str(event_payload.get(key)) != str(expected):
                return False
        return True

    def _resolve_channels(self, campaign: NotificationCampaign) -> list[str]:
        raw = campaign.channels if isinstance(campaign.channels, list) else []
        channels = [str(ch).strip().lower() for ch in raw if str(ch).strip()]
        return channels or self.DEFAULT_CHANNELS

    def _resolve_audience(self, campaign: NotificationCampaign) -> list[User]:
        rules: QuerySet[NotificationAudienceRule] = campaign.audience_rules.all()
        users_by_id: dict[int, User] = {}
        for rule in rules:
            q = User.objects.all()
            if rule.user_ids:
                q = q.filter(id__in=rule.user_ids)
            if rule.role_code:
                q = q.filter(role_code__iexact=rule.role_code)
            if rule.platform == NotificationBanner.PLATFORM_PARKPE:
                q = q.filter(is_active=True)
            for user in q[:2000]:
                users_by_id[user.id] = user
        if users_by_id:
            return list(users_by_id.values())
        # fallback for broad campaigns
        return list(User.objects.filter(is_active=True)[:1000])

    def _dispatch_single_channel(
        self,
        *,
        campaign: NotificationCampaign,
        user: User,
        channel: str,
        template: Optional[NotificationMessageTemplate],
        event_payload: dict,
    ) -> DispatchResult:
        try:
            if channel == NotificationMessageTemplate.CHANNEL_IN_APP:
                if not template:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="missing_template")
                UserNotification.objects.create(
                    user=user,
                    campaign=campaign,
                    channel=channel,
                    title=template.title or campaign.name,
                    message=template.body,
                    deep_link=template.cta_url or "",
                    metadata=event_payload,
                )
                return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_DELIVERED)

            if channel == NotificationMessageTemplate.CHANNEL_SMS:
                if not template:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="missing_template")
                profile = Profile.objects.filter(user=user).only("phone").first()
                phone = (getattr(profile, "phone", "") or "").strip()
                if not phone:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="phone_missing")
                res = NotificationServiceV2.send_sms(
                    phone_number=phone,
                    message=template.body,
                    user_id=user.id,
                    async_send=True,
                    context={"campaign_id": campaign.id},
                )
                status = NotificationDeliveryLog.STATUS_SENT if res.get("success") else NotificationDeliveryLog.STATUS_FAILED
                return DispatchResult(channel=channel, status=status, destination=phone, provider_message_id=str(res.get("task_id") or ""), response=res, error_message=str(res.get("message") or ""))

            if channel == NotificationMessageTemplate.CHANNEL_EMAIL:
                if not template:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="missing_template")
                email = (getattr(user, "email", "") or "").strip()
                if not email:
                    profile = Profile.objects.filter(user=user).only("email").first()
                    email = (getattr(profile, "email", "") or "").strip()
                if not email:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="email_missing")
                res = NotificationServiceV2.send_email(
                    to_email=email,
                    subject=template.subject or template.title or campaign.name,
                    plain_message=template.body,
                    user_id=user.id,
                    async_send=True,
                    use_parkpe=True,
                )
                status = NotificationDeliveryLog.STATUS_SENT if res.get("success") else NotificationDeliveryLog.STATUS_FAILED
                return DispatchResult(channel=channel, status=status, destination=email, provider_message_id=str(res.get("task_id") or ""), response=res, error_message=str(res.get("message") or ""))

            if channel == NotificationMessageTemplate.CHANNEL_PUSH:
                if not template:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="missing_template")
                if not getattr(settings, "NOTIFICATIONS_PUSH_ENABLED", False):
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_QUEUED, error_message="push_disabled_feature_flag")
                token = DevicePushToken.objects.filter(user=user, is_active=True).order_by("-updated_at").first()
                if not token:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="token_missing")
                # Provider integration placeholder. We log intent for phased rollout.
                return DispatchResult(
                    channel=channel,
                    status=NotificationDeliveryLog.STATUS_QUEUED,
                    destination=token.token[:18],
                    response={
                        "title": template.title or campaign.name,
                        "body": template.body,
                        "deepLink": template.cta_url,
                        "provider": "fcm_apns_pending",
                    },
                )

            if channel == NotificationMessageTemplate.CHANNEL_BANNER:
                if not template:
                    return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="missing_template")
                self._upsert_banner_from_template(campaign, template)
                return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_SENT)
        except Exception as exc:  # noqa: BLE001
            return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message=str(exc))
        return DispatchResult(channel=channel, status=NotificationDeliveryLog.STATUS_FAILED, error_message="unsupported_channel")

    def _upsert_banner_from_template(self, campaign: NotificationCampaign, template: NotificationMessageTemplate) -> None:
        payload = campaign.payload if isinstance(campaign.payload, dict) else {}
        banner_defaults = {
            "name": f"{campaign.name}-banner"[:120],
            "title": template.title or campaign.name,
            "message": template.body[:320],
            "cta_text": template.cta_text,
            "cta_url": template.cta_url,
            "image_url": template.image_url,
            "bg_color": str(payload.get("bg_color") or "#1f4f94")[:16],
            "text_color": str(payload.get("text_color") or "#ffffff")[:16],
            "platform": str(payload.get("platform") or NotificationBanner.PLATFORM_BOTH),
            "slot": str(payload.get("slot") or NotificationBanner.SLOT_SERVICE_INLINE),
            "service_code": str(payload.get("service_code") or "").lower(),
            "screen_code": str(payload.get("screen_code") or "").lower(),
            "priority": int(payload.get("priority") or 100),
            "starts_at": campaign.starts_at,
            "ends_at": campaign.ends_at,
            "is_active": campaign.status in (
                NotificationCampaign.STATUS_RUNNING,
                NotificationCampaign.STATUS_SCHEDULED,
            ),
        }
        NotificationBanner.objects.update_or_create(
            campaign=campaign,
            defaults=banner_defaults,
        )

    def _is_quiet_hour(self, campaign: NotificationCampaign, now_dt) -> bool:
        if not campaign.quiet_hours_start or not campaign.quiet_hours_end:
            return False
        now_time = now_dt.astimezone(timezone.get_current_timezone()).time()
        start: time = campaign.quiet_hours_start
        end: time = campaign.quiet_hours_end
        if start <= end:
            return start <= now_time <= end
        return now_time >= start or now_time <= end

    def _is_rollout_enabled(self, user: User) -> bool:
        if not getattr(settings, "NOTIFICATIONS_ENABLED", True):
            return False
        pct = int(getattr(settings, "NOTIFICATIONS_ROLLOUT_PERCENT", 100) or 100)
        pct = max(0, min(100, pct))
        if pct >= 100:
            return True
        if pct <= 0:
            return False
        return (int(user.id) % 100) < pct

    def _is_rate_limited(self, user: User) -> bool:
        per_hour = int(getattr(settings, "NOTIFICATIONS_RATE_LIMIT_PER_USER", 50) or 50)
        if per_hour <= 0:
            return False
        one_hour_ago = timezone.now() - timedelta(hours=1)
        count = NotificationDeliveryLog.objects.filter(
            user=user,
            created_at__gte=one_hour_ago,
        ).exclude(status=NotificationDeliveryLog.STATUS_FAILED).count()
        return count >= per_hour

    def _log_result(
        self,
        campaign: NotificationCampaign,
        user: User,
        channel: str,
        result: DispatchResult,
        actor_id: Optional[int],
        event_payload: Optional[dict],
    ) -> None:
        self._log(
            campaign=campaign,
            user=user,
            channel=channel,
            status=result.status,
            destination=result.destination,
            provider_message_id=result.provider_message_id,
            request_payload={"actor_id": actor_id, "event_payload": event_payload or {}},
            response_payload=result.response or {},
            error_message=result.error_message,
        )

    def _log(
        self,
        *,
        campaign: NotificationCampaign,
        user: Optional[User],
        channel: str,
        status: str,
        destination: str = "",
        provider_message_id: str = "",
        request_payload: Optional[dict] = None,
        response_payload: Optional[dict] = None,
        error_message: str = "",
    ) -> None:
        NotificationDeliveryLog.objects.create(
            campaign=campaign,
            user=user,
            channel=channel,
            status=status,
            destination=destination,
            provider="notification_orchestrator",
            provider_message_id=provider_message_id,
            request_payload=request_payload or {},
            response_payload=response_payload or {},
            error_message=error_message[:1500],
        )
