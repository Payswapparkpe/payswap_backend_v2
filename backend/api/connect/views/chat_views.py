"""
ParkPe Connect API – predefined messages, threads, messages, report.
"""
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models import Q, Max
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import JSONParser

from ..profanity_filter import contains_profanity, user_facing_block_message
from ..risk_controls import check_chat_abuse, report_unique_reporters_count

from ._common import vehicle_log

from portal.models import (
    VehicleQRCode,
    Vehicle,
    User,
    ConnectPredefinedMessage,
    ConnectThread,
    ConnectMessage,
    ConnectReport,
    Profile,
    ConnectModerationAction,
)

from api.throttling import ConnectChatPollThrottle, ConnectChatRateThrottle
from portal.services.connect_attachment_storage import persist_connect_binary_from_data_url
from portal.services.connect_chat_notifications import (
    create_connect_message_notification,
    thread_muted_for_participant,
)
from .vehicle_views import _mask_registration, _owner_display_name


def _chat_peer_display_name(user: User | None) -> str:
    """
    Display name for Connect chat (header / inbox). Uses profile first name — never phone numbers.
    """
    if user is None:
        return "User"
    profile = getattr(user, "profile", None)
    if profile:
        fn = (getattr(profile, "first_name", None) or "").strip()
        if fn:
            return fn
    fn = (getattr(user, "first_name", None) or "").strip()
    if fn:
        return fn
    un = (user.username or "").strip()
    if un:
        return un
    return "User"


def _peer_user_for_thread(thread: ConnectThread, viewer_user_id: int) -> User | None:
    """The other participant (vehicle owner ↔ scanner)."""
    if thread.vehicle.user_id == viewer_user_id:
        return thread.scanner_user
    if thread.scanner_user_id == viewer_user_id:
        return thread.vehicle.user
    return None


PRESENCE_TTL_SECONDS = 120
TYPING_TTL_SECONDS = 8


def _participant_kind(thread: ConnectThread, user_id: int):
    if thread.vehicle.user_id == user_id:
        return "owner"
    if thread.scanner_user_id == user_id:
        return "scanner"
    return None


def _participant_settings(thread: ConnectThread, user_id: int):
    kind = _participant_kind(thread, user_id)
    if kind == "owner":
        return {
            "kind": kind,
            "is_owner": True,
            "other_user_id": thread.scanner_user_id,
            "pinned": thread.owner_pinned,
            "muted": thread.owner_muted,
            "archived": thread.owner_archived,
            "last_read_message_id": thread.owner_last_read_message_id,
            "last_seen_at": thread.owner_last_seen_at,
        }
    if kind == "scanner":
        return {
            "kind": kind,
            "is_owner": False,
            "other_user_id": thread.vehicle.user_id,
            "pinned": thread.scanner_pinned,
            "muted": thread.scanner_muted,
            "archived": thread.scanner_archived,
            "last_read_message_id": thread.scanner_last_read_message_id,
            "last_seen_at": thread.scanner_last_seen_at,
        }
    return None


def _presence_key(thread_id: int, user_id: int):
    return f"connect:presence:{thread_id}:{user_id}"


def _typing_key(thread_id: int, user_id: int):
    return f"connect:typing:{thread_id}:{user_id}"


def _set_presence(thread_id: int, user_id: int):
    cache.set(_presence_key(thread_id, user_id), "1", timeout=PRESENCE_TTL_SECONDS)


def _set_typing(thread_id: int, user_id: int, is_typing: bool):
    key = _typing_key(thread_id, user_id)
    if is_typing:
        cache.set(key, "1", timeout=TYPING_TTL_SECONDS)
    else:
        cache.delete(key)


def _serialize_message(m: ConnectMessage):
    meta = dict(m.metadata or {})
    sp = meta.get("storage_path")
    if sp and "data_url" not in meta:
        try:
            meta = {**meta, "media_url": default_storage.url(sp)}
        except Exception:
            pass
    return {
        "id": m.id,
        "sender_id": m.sender_id,
        "message_type": m.message_type,
        "body": m.body,
        "metadata": meta,
        "client_id": m.client_id or "",
        "delivery_status": m.delivery_status,
        "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
        "seen_at": m.seen_at.isoformat() if m.seen_at else None,
        "predefined_code": m.predefined_message.code if m.predefined_message else None,
        "created_at": m.created_at.isoformat(),
    }


class ConnectPredefinedMessagesView(APIView):
    """GET /api/connect/chat/predefined-messages/ – list active predefined messages (public or auth)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        qs = ConnectPredefinedMessage.objects.filter(is_active=True).order_by('order', 'code')
        data = [
            {
                "code": m.code,
                "label_en": m.label_en,
                "label_hi": m.label_hi or m.label_en,
                "body_en": m.body_en,
                "body_hi": m.body_hi or m.body_en,
            }
            for m in qs
        ]
        return Response(data)


class ConnectThreadListCreateView(APIView):
    """GET /api/connect/chat/threads/ – list my threads. POST – create or get thread by qr_code."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request):
        threads = ConnectThread.objects.filter(
            Q(vehicle__user=request.user) | Q(scanner_user=request.user),
            vehicle__connect_scope=Vehicle.SCOPE_CONSUMER,
        ).select_related(
            'vehicle',
            'vehicle__user',
            'vehicle__user__profile',
            'scanner_user',
            'scanner_user__profile',
        ).distinct().order_by('-updated_at')[:100]
        out = []
        for t in threads:
            vehicle = t.vehicle
            owner_name = _owner_display_name(vehicle)
            settings = _participant_settings(t, request.user.pk)
            if not settings:
                continue
            other_id = settings["other_user_id"]
            peer_user = _peer_user_for_thread(t, request.user.pk)
            peer_display_name = _chat_peer_display_name(peer_user)
            last_message = t.messages.order_by("-id").first()
            unread_count = 0
            if settings["last_read_message_id"]:
                unread_count = t.messages.filter(
                    sender_id=other_id,
                    id__gt=settings["last_read_message_id"],
                ).count()
            else:
                unread_count = t.messages.filter(sender_id=other_id).count()
            out.append({
                "id": t.id,
                "vehicle_id": vehicle.id,
                "registration_number_masked": _mask_registration(vehicle.registration_number),
                "owner_display_name": owner_name,
                "peer_display_name": peer_display_name,
                "scanner_user_id": t.scanner_user_id,
                "is_owner": settings["is_owner"],
                "other_participant_id": other_id,
                "pinned": settings["pinned"],
                "muted": settings["muted"],
                "archived": settings["archived"],
                "last_read_message_id": settings["last_read_message_id"],
                "last_message_id": last_message.id if last_message else None,
                "last_message_preview": (last_message.body[:120] if last_message else ""),
                "last_message_created_at": (last_message.created_at.isoformat() if last_message else None),
                "unread_count": unread_count,
            })
        return Response(out)

    def post(self, request):
        qr_code = (request.data.get("qr_code") or "").strip()
        if not qr_code:
            return Response({"detail": "qr_code is required."}, status=status.HTTP_400_BAD_REQUEST)
        qr = VehicleQRCode.objects.select_related('vehicle', 'vehicle__user').filter(code=qr_code).first()
        if not qr:
            return Response({"detail": "Invalid or expired QR code."}, status=status.HTTP_404_NOT_FOUND)
        vehicle = qr.vehicle
        if vehicle.connect_scope != Vehicle.SCOPE_CONSUMER:
            return Response({"detail": "Invalid or expired QR code."}, status=status.HTTP_404_NOT_FOUND)
        if vehicle.user_id == request.user.pk:
            return Response(
                {"detail": "You cannot start a chat on your own vehicle QR."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        thread, created = ConnectThread.objects.get_or_create(
            vehicle=vehicle,
            scanner_user=request.user,
        )
        thread = ConnectThread.objects.select_related(
            "vehicle",
            "vehicle__user",
            "vehicle__user__profile",
            "scanner_user",
            "scanner_user__profile",
        ).get(pk=thread.pk)
        owner_user = thread.vehicle.user
        peer_display_name = _chat_peer_display_name(owner_user)
        return Response({
            "id": thread.id,
            "vehicle_id": vehicle.id,
            "registration_number_masked": _mask_registration(vehicle.registration_number),
            "owner_display_name": _owner_display_name(vehicle),
            "peer_display_name": peer_display_name,
            "other_participant_id": vehicle.user_id,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ConnectThreadDetailView(APIView):
    """GET /api/connect/chat/threads/<id>/ – single thread (participant only)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        thread = ConnectThread.objects.filter(
            pk=pk
        ).select_related(
            'vehicle',
            'vehicle__user',
            'vehicle__user__profile',
            'scanner_user',
            'scanner_user__profile',
        ).first()
        if not thread:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if thread.vehicle.user_id != request.user.pk and thread.scanner_user_id != request.user.pk:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        vehicle = thread.vehicle
        settings = _participant_settings(thread, request.user.pk)
        if not settings:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        other_id = settings["other_user_id"]
        peer_user = _peer_user_for_thread(thread, request.user.pk)
        peer_display_name = _chat_peer_display_name(peer_user)
        _set_presence(thread.id, request.user.pk)
        return Response({
            "id": thread.id,
            "vehicle_id": vehicle.id,
            "registration_number_masked": _mask_registration(vehicle.registration_number),
            "owner_display_name": _owner_display_name(vehicle),
            "peer_display_name": peer_display_name,
            "scanner_user_id": thread.scanner_user_id,
            "is_owner": settings["is_owner"],
            "other_participant_id": other_id,
            "pinned": settings["pinned"],
            "muted": settings["muted"],
            "archived": settings["archived"],
            "last_read_message_id": settings["last_read_message_id"],
            "other_online": bool(cache.get(_presence_key(thread.id, other_id))),
            "other_typing": bool(cache.get(_typing_key(thread.id, other_id))),
        })


class ConnectThreadMessagesView(APIView):
    """GET /api/connect/chat/threads/<id>/messages/ – list messages (paginated). POST – send message."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_throttles(self):
        if self.request.method == "GET":
            return [ConnectChatPollThrottle()]
        return [ConnectChatRateThrottle()]

    def _get_thread_or_404(self, request, pk):
        thread = ConnectThread.objects.filter(pk=pk).select_related('vehicle', 'vehicle__user', 'scanner_user').first()
        if not thread:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if thread.vehicle.user_id != request.user.pk and thread.scanner_user_id != request.user.pk:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return thread, None

    def get(self, request, pk):
        thread, err = self._get_thread_or_404(request, pk)
        if err:
            return err
        participant = _participant_settings(thread, request.user.pk)
        if not participant:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        _set_presence(thread.id, request.user.pk)
        after = request.query_params.get("after")
        before = request.query_params.get("before")
        qs = ConnectMessage.objects.filter(thread=thread).select_related('sender', 'predefined_message').order_by('created_at')
        if after:
            try:
                after_id = int(after)
                qs = qs.filter(id__gt=after_id)
            except ValueError:
                pass
        elif before:
            try:
                before_id = int(before)
                qs = qs.filter(id__lt=before_id).order_by('-created_at')
                messages = list(reversed(list(qs[:50])))
            except ValueError:
                messages = list(qs[:50])
        else:
            messages = list(qs[:50])
        if after:
            messages = list(qs[:50])
        # Mark delivery for incoming unseen delivered states.
        incoming = [m.id for m in messages if m.sender_id != request.user.pk and m.delivery_status == "sent"]
        if incoming:
            now = timezone.now()
            ConnectMessage.objects.filter(id__in=incoming).update(delivery_status="delivered", delivered_at=now)
            for m in messages:
                if m.id in incoming:
                    m.delivery_status = "delivered"
                    m.delivered_at = now
        data = [_serialize_message(m) for m in messages]
        return Response(data)

    def post(self, request, pk):
        thread, err = self._get_thread_or_404(request, pk)
        if err:
            return err
        sender_profile = getattr(request.user, "profile", None)
        if sender_profile and getattr(sender_profile, "connect_blocked_until", None):
            if timezone.now() < sender_profile.connect_blocked_until:
                return Response(
                    {"detail": "You are temporarily blocked from Connect. Contact support if you believe this is an error."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        msg_type = (request.data.get("message_type") or "text").strip()
        body = (request.data.get("body") or "").strip()
        metadata = request.data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        client_id = (request.data.get("client_id") or "").strip()
        predefined_code = (request.data.get("predefined_code") or "").strip()
        pref = None
        if msg_type == "predefined":
            if not predefined_code:
                return Response({"detail": "predefined_code is required for message_type predefined."}, status=status.HTTP_400_BAD_REQUEST)
            pref = ConnectPredefinedMessage.objects.filter(code=predefined_code, is_active=True).first()
            if not pref:
                return Response({"detail": "Invalid predefined message code."}, status=status.HTTP_400_BAD_REQUEST)
            body = pref.body_en
        elif msg_type == "text":
            if not body:
                return Response({"detail": "body is required for text message."}, status=status.HTTP_400_BAD_REQUEST)
        elif msg_type in ("attachment", "voice"):
            if not body:
                return Response({"detail": "body is required for attachment/voice message."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"detail": "message_type must be text/predefined/attachment/voice."}, status=status.HTTP_400_BAD_REQUEST)
        recipient_user_id = thread.scanner_user_id if thread.vehicle.user_id == request.user.pk else thread.vehicle.user_id

        if msg_type in ("text", "attachment", "voice") and body and contains_profanity(body):
            just_temp_blocked = False
            if sender_profile:
                sender_profile.connect_warning_count = max(
                    0, int(getattr(sender_profile, "connect_warning_count", 0) or 0) + 1
                )
                update_fields = ["connect_warning_count"]
                threshold = int(getattr(settings, "CONNECT_PROFANITY_AUTO_BLOCK_THRESHOLD", 0) or 0)
                if threshold > 0:
                    bucket = timezone.now().strftime("%Y%m%d%H")
                    hit_key = f"connect_prof_attempt:{request.user.pk}:{bucket}"
                    hits = int(cache.get(hit_key) or 0) + 1
                    cache.set(hit_key, hits, timeout=3900)
                    if hits >= threshold:
                        minutes = max(1, int(getattr(settings, "CONNECT_PROFANITY_AUTO_BLOCK_MINUTES", 60) or 60))
                        sender_profile.connect_blocked_until = timezone.now() + timedelta(minutes=minutes)
                        update_fields.append("connect_blocked_until")
                        just_temp_blocked = True
                        vehicle_log(
                            request,
                            "WARNING",
                            "connect_chat_profanity_auto_blocked",
                            {"user_id": request.user.pk, "thread_id": thread.pk, "hits": hits},
                        )
                sender_profile.save(update_fields=update_fields)
            vehicle_log(
                request,
                "WARNING",
                "connect_chat_profanity_blocked",
                {"user_id": request.user.pk, "thread_id": thread.pk},
            )
            detail_msg = user_facing_block_message()
            if just_temp_blocked:
                detail_msg = getattr(settings, "CONNECT_PROFANITY_AUTO_BLOCK_MESSAGE", None) or (
                    "Repeated unacceptable language. Connect chat is temporarily restricted. "
                    "/ बार-बार गलत भाषा के कारण Connect अस्थायी रूप से बंद कर दिया गया है।"
                )
            payload = {
                "detail": detail_msg,
                "code": "connect_profanity",
                "warning": True,
            }
            if just_temp_blocked:
                payload["connect_temp_blocked"] = True
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        risk_decision = check_chat_abuse(
            request,
            sender_user_id=request.user.pk,
            thread_id=thread.pk,
            recipient_user_id=recipient_user_id,
            body=body,
        )
        if not risk_decision.allowed:
            return Response(
                {
                    "detail": "Message blocked for safety policy.",
                    "code": "connect_chat_policy_block",
                    "risk_reasons": risk_decision.reasons,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if msg_type in ("attachment", "voice"):
            try:
                metadata = persist_connect_binary_from_data_url(thread.pk, metadata)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        msg = ConnectMessage.objects.create(
            thread=thread,
            sender=request.user,
            message_type=msg_type,
            body=body,
            metadata=metadata,
            client_id=client_id,
            predefined_message=pref,
        )
        thread.save(update_fields=["updated_at"])
        try:
            create_connect_message_notification(thread=thread, message=msg, sender=request.user)
        except Exception:
            pass
        # Notify the other participant via SMS (async, non-blocking; muted threads skip SMS)
        try:
            from portal.tasks.notification_tasks import send_sms_task
            is_sender_owner = thread.vehicle.user_id == request.user.pk
            recipient_user = thread.scanner_user if is_sender_owner else thread.vehicle.user
            recipient_profile = getattr(recipient_user, "profile", None)
            recipient_phone = (getattr(recipient_profile, "phone", None) or "").strip()
            if recipient_phone and not thread_muted_for_participant(thread, recipient_user.pk):
                display_reg = _mask_registration(thread.vehicle.registration_number or "")
                send_sms_task.delay(
                    phone_number=recipient_phone,
                    message=f"New message on ParkPe Connect for vehicle {display_reg}. Open the ParkPe app to reply.",
                )
        except Exception:
            pass
        return Response(_serialize_message(msg), status=status.HTTP_201_CREATED)


class ConnectThreadMarkReadView(APIView):
    """POST /api/connect/chat/threads/<id>/mark-read/ – mark thread read till latest message."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, pk):
        thread = ConnectThread.objects.filter(pk=pk).select_related("vehicle").first()
        if not thread:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        participant = _participant_settings(thread, request.user.pk)
        if not participant:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        max_id = thread.messages.aggregate(mx=Max("id")).get("mx") or 0
        now = timezone.now()
        update_fields = []
        if participant["kind"] == "owner":
            thread.owner_last_read_message_id = max_id
            thread.owner_last_seen_at = now
            update_fields.extend(["owner_last_read_message_id", "owner_last_seen_at"])
        else:
            thread.scanner_last_read_message_id = max_id
            thread.scanner_last_seen_at = now
            update_fields.extend(["scanner_last_read_message_id", "scanner_last_seen_at"])
        thread.save(update_fields=update_fields)
        _set_presence(thread.id, request.user.pk)
        # Mark opposite participant messages as seen up to max_id.
        ConnectMessage.objects.filter(
            thread=thread,
            id__lte=max_id,
            sender_id=participant["other_user_id"],
        ).exclude(delivery_status="seen").update(delivery_status="seen", seen_at=now, delivered_at=now)
        return Response({"ok": True, "last_read_message_id": max_id})


class ConnectThreadPresenceView(APIView):
    """POST heartbeat and typing state, GET other participant presence."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, pk):
        thread = ConnectThread.objects.filter(pk=pk).select_related("vehicle").first()
        if not thread:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        participant = _participant_settings(thread, request.user.pk)
        if not participant:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        _set_presence(thread.id, request.user.pk)
        _set_typing(thread.id, request.user.pk, bool(request.data.get("typing")))
        return Response({"ok": True})

    def get(self, request, pk):
        thread = ConnectThread.objects.filter(pk=pk).select_related("vehicle").first()
        if not thread:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        participant = _participant_settings(thread, request.user.pk)
        if not participant:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        _set_presence(thread.id, request.user.pk)
        other_id = participant["other_user_id"]
        return Response({
            "other_online": bool(cache.get(_presence_key(thread.id, other_id))),
            "other_typing": bool(cache.get(_typing_key(thread.id, other_id))),
        })


class ConnectThreadSettingsView(APIView):
    """PATCH /api/connect/chat/threads/<id>/settings/ – pin/mute/archive for current participant."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def patch(self, request, pk):
        thread = ConnectThread.objects.filter(pk=pk).select_related("vehicle").first()
        if not thread:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        participant = _participant_settings(thread, request.user.pk)
        if not participant:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        update_fields = []
        for key in ("pinned", "muted", "archived"):
            if key not in request.data:
                continue
            value = bool(request.data.get(key))
            setattr(thread, f"{participant['kind']}_{key}", value)
            update_fields.append(f"{participant['kind']}_{key}")
        if not update_fields:
            return Response({"detail": "At least one of pinned/muted/archived is required."}, status=status.HTTP_400_BAD_REQUEST)
        thread.save(update_fields=update_fields)
        return Response({
            "pinned": getattr(thread, f"{participant['kind']}_pinned"),
            "muted": getattr(thread, f"{participant['kind']}_muted"),
            "archived": getattr(thread, f"{participant['kind']}_archived"),
        })


class ConnectThreadBlockView(APIView):
    """POST /api/connect/chat/threads/<id>/block/ - block or unblock other participant."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, pk):
        thread = ConnectThread.objects.filter(pk=pk).select_related("vehicle", "vehicle__user", "scanner_user").first()
        if not thread:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        participant = _participant_settings(thread, request.user.pk)
        if not participant:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        action = (request.data.get("action") or "block").strip().lower()
        target_user = User.objects.filter(pk=participant["other_user_id"]).first()
        if not target_user:
            return Response({"detail": "Other participant not found."}, status=status.HTTP_404_NOT_FOUND)
        target_profile = getattr(target_user, "profile", None)
        if not target_profile:
            return Response({"detail": "User profile not found."}, status=status.HTTP_404_NOT_FOUND)
        if action == "unblock":
            target_profile.connect_blocked_until = None
            target_profile.save(update_fields=["connect_blocked_until"])
            ConnectModerationAction.objects.create(
                actor_user=request.user,
                target_user=target_user,
                action=ConnectModerationAction.ACTION_UNBLOCK,
                reason=(request.data.get("reason") or "").strip(),
                metadata={"source": "connect_chat_thread", "thread_id": thread.id},
            )
            return Response({"blocked": False, "message": "User unblocked."})
        target_profile.connect_blocked_until = timezone.now() + timedelta(hours=24)
        target_profile.save(update_fields=["connect_blocked_until"])
        ConnectModerationAction.objects.create(
            actor_user=request.user,
            target_user=target_user,
            action=ConnectModerationAction.ACTION_TEMP_BLOCK,
            reason=(request.data.get("reason") or "").strip(),
            metadata={"source": "connect_chat_thread", "thread_id": thread.id},
        )
        return Response({"blocked": True, "message": "User blocked for 24h."})


class ConnectReportCreateView(APIView):
    """POST /api/connect/report/ – report a user (e.g. from chat). Body: thread_id, reported_user_id, reason."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        thread_id = request.data.get("thread_id")
        reported_user_id = request.data.get("reported_user_id")
        reason = (request.data.get("reason") or "").strip()
        if not thread_id or not reported_user_id or not reason:
            return Response(
                {"detail": "thread_id, reported_user_id and reason are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            thread_id = int(thread_id)
            reported_user_id = int(reported_user_id)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid thread_id or reported_user_id."}, status=status.HTTP_400_BAD_REQUEST)
        thread = ConnectThread.objects.filter(pk=thread_id).select_related("vehicle", "vehicle__user").first()
        if not thread:
            return Response({"detail": "Thread not found."}, status=status.HTTP_404_NOT_FOUND)
        if thread.vehicle.user_id != request.user.pk and thread.scanner_user_id != request.user.pk:
            return Response({"detail": "You are not a participant in this thread."}, status=status.HTTP_403_FORBIDDEN)
        if reported_user_id == request.user.pk:
            return Response({"detail": "You cannot report yourself."}, status=status.HTTP_400_BAD_REQUEST)
        other_participant_id = thread.vehicle.user_id if thread.scanner_user_id == request.user.pk else thread.scanner_user_id
        if reported_user_id != other_participant_id:
            return Response({"detail": "Reported user must be the other participant in this thread."}, status=status.HTTP_400_BAD_REQUEST)
        reported_user = User.objects.filter(pk=reported_user_id).first()
        if not reported_user:
            return Response({"detail": "Reported user not found."}, status=status.HTTP_404_NOT_FOUND)
        report = ConnectReport.objects.create(
            reporter_user=request.user,
            reported_user=reported_user,
            thread=thread,
            reason=reason,
            status="pending",
        )
        report_count = ConnectReport.objects.filter(reported_user=reported_user).count()
        unique_reporters_24h = report_unique_reporters_count(reported_user.pk, within_hours=24)
        reported_profile = getattr(reported_user, "profile", None)
        if reported_profile:
            reported_profile.connect_warning_count = report_count
            if unique_reporters_24h >= 3:
                blocked_until = timezone.now() + timedelta(hours=24)
                current_block_until = getattr(reported_profile, "connect_blocked_until", None)
                if not current_block_until or current_block_until < blocked_until:
                    reported_profile.connect_blocked_until = blocked_until
            reported_profile.save(update_fields=["connect_warning_count", "connect_blocked_until"])
        return Response({
            "id": report.id,
            "status": report.status,
            "message": "Report submitted. Our team will review it.",
            "warning_count": report_count,
            "unique_reporters_24h": unique_reporters_24h,
        }, status=status.HTTP_201_CREATED)
