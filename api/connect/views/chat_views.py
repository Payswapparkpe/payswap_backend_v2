"""
ParkPe Connect API – predefined messages, threads, messages, report.
"""
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import JSONParser

from portal.models import (
    VehicleQRCode,
    Vehicle,
    User,
    ConnectPredefinedMessage,
    ConnectThread,
    ConnectMessage,
    ConnectReport,
    Profile,
)

from api.throttling import ConnectChatRateThrottle
from .vehicle_views import _mask_registration, _owner_display_name


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
            Q(vehicle__user=request.user) | Q(scanner_user=request.user)
        ).select_related('vehicle', 'vehicle__user', 'scanner_user').distinct().order_by('-updated_at')[:100]
        out = []
        for t in threads:
            vehicle = t.vehicle
            owner_name = _owner_display_name(vehicle)
            is_owner = vehicle.user.pk == request.user.pk
            other_id = t.scanner_user_id if is_owner else vehicle.user_id
            out.append({
                "id": t.id,
                "vehicle_id": vehicle.id,
                "registration_number_masked": _mask_registration(vehicle.registration_number),
                "owner_display_name": owner_name,
                "scanner_user_id": t.scanner_user_id,
                "is_owner": is_owner,
                "other_participant_id": other_id,
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
        thread, created = ConnectThread.objects.get_or_create(
            vehicle=vehicle,
            scanner_user=request.user,
        )
        return Response({
            "id": thread.id,
            "vehicle_id": vehicle.id,
            "registration_number_masked": _mask_registration(vehicle.registration_number),
            "owner_display_name": _owner_display_name(vehicle),
            "other_participant_id": vehicle.user_id,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ConnectThreadDetailView(APIView):
    """GET /api/connect/chat/threads/<id>/ – single thread (participant only)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        thread = ConnectThread.objects.filter(
            pk=pk
        ).select_related('vehicle', 'vehicle__user', 'scanner_user').first()
        if not thread:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if thread.vehicle.user_id != request.user.pk and thread.scanner_user_id != request.user.pk:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        vehicle = thread.vehicle
        is_owner = vehicle.user_id == request.user.pk
        other_id = thread.scanner_user_id if is_owner else vehicle.user_id
        return Response({
            "id": thread.id,
            "vehicle_id": vehicle.id,
            "registration_number_masked": _mask_registration(vehicle.registration_number),
            "owner_display_name": _owner_display_name(vehicle),
            "scanner_user_id": thread.scanner_user_id,
            "is_owner": is_owner,
            "other_participant_id": other_id,
        })


class ConnectThreadMessagesView(APIView):
    """GET /api/connect/chat/threads/<id>/messages/ – list messages (paginated). POST – send message."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_classes = [ConnectChatRateThrottle]

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
        data = [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "message_type": m.message_type,
                "body": m.body,
                "predefined_code": m.predefined_message.code if m.predefined_message else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
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
        else:
            return Response({"detail": "message_type must be 'text' or 'predefined'."}, status=status.HTTP_400_BAD_REQUEST)
        msg = ConnectMessage.objects.create(
            thread=thread,
            sender=request.user,
            message_type=msg_type,
            body=body,
            predefined_message=pref,
        )
        thread.save(update_fields=["updated_at"])
        # Notify the other participant via SMS (async, non-blocking)
        try:
            from portal.tasks.notification_tasks import send_sms_task
            is_sender_owner = thread.vehicle.user_id == request.user.pk
            recipient_user = thread.scanner_user if is_sender_owner else thread.vehicle.user
            recipient_profile = getattr(recipient_user, "profile", None)
            recipient_phone = (getattr(recipient_profile, "phone", None) or "").strip()
            if recipient_phone:
                masked_reg = thread.vehicle.registration_number[:4] + "****"
                send_sms_task.delay(
                    phone_number=recipient_phone,
                    message=f"New message on ParkPe Connect for vehicle {masked_reg}. Open the ParkPe app to reply.",
                )
        except Exception:
            pass
        return Response({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "message_type": msg.message_type,
            "body": msg.body,
            "predefined_code": msg.predefined_message.code if msg.predefined_message else None,
            "created_at": msg.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


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
        # Use lifetime report count so admins resolving old reports don't reset the ban threshold
        report_count = ConnectReport.objects.filter(reported_user=reported_user).count()
        reported_profile = getattr(reported_user, "profile", None)
        if reported_profile:
            reported_profile.connect_warning_count = report_count
            if report_count >= 3:
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
        }, status=status.HTTP_201_CREATED)
