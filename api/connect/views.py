"""
ParkPe Connect API – vehicle CRUD, by-QR lookup, masked call (Kaleyra click-to-call).
"""
import secrets
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser

from portal.models import Vehicle, VehicleQRCode
from .serializers import (
    VehicleSerializer,
    VehicleCreateSerializer,
    VehicleByQRResponseSerializer,
)


def _mask_registration(reg: str) -> str:
    """Mask registration number for public display (e.g. KA01AB****)."""
    if not reg or len(reg) < 4:
        return "****"
    return reg[:4].upper() + "*" * min(len(reg) - 4, 4)


def _owner_display_name(vehicle: Vehicle) -> str:
    """Non-PII display name for vehicle owner (e.g. 'Vehicle Owner')."""
    user = vehicle.user
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "first_name", None):
        return f"{profile.first_name.strip()}***"
    return "Vehicle Owner"


class VehicleListCreateView(APIView):
    """GET /api/connect/vehicles/ – list my vehicles. POST – create vehicle (and QR)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        qs = Vehicle.objects.filter(user=request.user).select_related('qr_code').order_by('-is_primary', '-created_at')
        serializer = VehicleSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        data['user'] = request.user.id
        serializer = VehicleCreateSerializer(data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        reg = (serializer.validated_data.get('registration_number') or '').strip().upper()
        if Vehicle.objects.filter(user=request.user, registration_number=reg).exists():
            return Response(
                {"detail": "A vehicle with this registration number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vehicle = serializer.save(user=request.user)
        # Create unique QR code for this vehicle
        code = secrets.token_urlsafe(10).replace('-', '').replace('_', '')[:14]
        while VehicleQRCode.objects.filter(code=code).exists():
            code = secrets.token_urlsafe(10).replace('-', '').replace('_', '')[:14]
        VehicleQRCode.objects.create(vehicle=vehicle, code=code)
        vehicle.refresh_from_db()
        return Response(
            VehicleSerializer(vehicle).data,
            status=status.HTTP_201_CREATED,
        )


class VehicleDetailView(APIView):
    """GET /api/connect/vehicles/<id>/ – get one. PATCH – update. DELETE – delete."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _get_vehicle(self, request, pk):
        return Vehicle.objects.filter(user=request.user).select_related('qr_code').filter(pk=pk).first()

    def get(self, request, pk):
        vehicle = self._get_vehicle(request, pk)
        if not vehicle:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(VehicleSerializer(vehicle).data)

    def patch(self, request, pk):
        vehicle = self._get_vehicle(request, pk)
        if not vehicle:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = VehicleCreateSerializer(vehicle, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        reg = (serializer.validated_data.get('registration_number') or vehicle.registration_number).strip().upper()
        if reg != vehicle.registration_number and Vehicle.objects.filter(user=request.user, registration_number=reg).exists():
            return Response(
                {"detail": "Another vehicle with this registration number already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        vehicle.refresh_from_db()
        return Response(VehicleSerializer(vehicle).data)

    def delete(self, request, pk):
        vehicle = self._get_vehicle(request, pk)
        if not vehicle:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        vehicle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleQRView(APIView):
    """GET /api/connect/vehicles/<id>/qr/ – get QR code string and optional image URL for owner."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        vehicle = Vehicle.objects.filter(user=request.user).select_related('qr_code').filter(pk=pk).first()
        if not vehicle:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        qr = getattr(vehicle, 'qr_code', None)
        if not qr:
            return Response({"detail": "QR code not found for this vehicle."}, status=status.HTTP_404_NOT_FOUND)
        # Frontend should build full scan URL from its origin (e.g. window.location.origin + scan_path)
        scan_path = f"/connect/scan/{qr.code}"
        return Response({
            "qr_code": qr.code,
            "scan_path": scan_path,
            "scan_url": request.build_absolute_uri(scan_path),
        })


def _vehicle_by_qr_payload(qr, vehicle):
    """Build public scan payload for a vehicle + its QR."""
    return {
        "vehicle_id": vehicle.id,
        "qr_code": qr.code,
        "registration_number_masked": _mask_registration(vehicle.registration_number),
        "brand": vehicle.brand or "",
        "model": vehicle.model or "",
        "year": vehicle.year,
        "owner_display_name": _owner_display_name(vehicle),
        "contact_options": ["call", "chat"],
    }


class VehicleByQRView(APIView):
    """GET /api/connect/vehicle/by-qr/<qr_code>/ – public; masked vehicle + contact options."""
    permission_classes = [AllowAny]

    def get(self, request, qr_code):
        qr = VehicleQRCode.objects.select_related('vehicle', 'vehicle__user').filter(code=qr_code.strip()).first()
        if not qr:
            return Response({"detail": "Invalid or expired QR code."}, status=status.HTTP_404_NOT_FOUND)
        vehicle = qr.vehicle
        payload = _vehicle_by_qr_payload(qr, vehicle)
        serializer = VehicleByQRResponseSerializer(payload)
        return Response(serializer.data)


def _normalize_registration(reg: str) -> str:
    """Normalize for lookup: strip, upper, single spaces removed."""
    if not reg:
        return ""
    return "".join(reg.strip().upper().split())


class VehicleByRegistrationView(APIView):
    """GET /api/connect/vehicle/by-registration/<registration_number>/ – public; same as by-qr for scan flow."""
    permission_classes = [AllowAny]

    def get(self, request, registration_number):
        norm = _normalize_registration(registration_number)
        if not norm or len(norm) < 2:
            return Response(
                {"detail": "Enter a valid vehicle registration number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Exact match (case-insensitive, no spaces)
        vehicle = Vehicle.objects.filter(registration_number__iexact=norm).select_related("user").first()
        if not vehicle:
            # Match normalized: user may have stored "KA 01 AB 1234"
            for v in Vehicle.objects.select_related("user").all():
                if _normalize_registration(v.registration_number) == norm:
                    vehicle = v
                    break
        if not vehicle:
            return Response(
                {"detail": "No Connect vehicle found with this registration number."},
                status=status.HTTP_404_NOT_FOUND,
            )
        qr = VehicleQRCode.objects.filter(vehicle=vehicle).first()
        if not qr:
            return Response(
                {"detail": "This vehicle is not linked to a Connect QR yet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload = _vehicle_by_qr_payload(qr, vehicle)
        serializer = VehicleByQRResponseSerializer(payload)
        return Response(serializer.data)


class ConnectCallInitiateView(APIView):
    """POST /api/connect/call/initiate – masked call via Kaleyra click-to-call. Body: qr_code, scanner_phone."""
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        qr_code = (request.data.get("qr_code") or "").strip()
        scanner_phone = (request.data.get("scanner_phone") or "").strip()
        if not qr_code or not scanner_phone:
            return Response(
                {"detail": "qr_code and scanner_phone are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qr = VehicleQRCode.objects.select_related("vehicle", "vehicle__user", "vehicle__user__profile").filter(
            code=qr_code
        ).first()
        if not qr:
            return Response({"detail": "Invalid or expired QR code."}, status=status.HTTP_404_NOT_FOUND)
        vehicle = qr.vehicle
        owner = vehicle.user
        profile = getattr(owner, "profile", None)
        owner_phone = (getattr(profile, "phone", None) or "").strip()
        if not owner_phone:
            return Response(
                {"detail": "Vehicle owner has no phone number registered."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from portal.services.vendors.kaleyra import KaleyraClient
            client = KaleyraClient()
            # from = called first (scanner), to = owner; both connect via bridge (masked)
            result = client.click_to_call(
                from_number=scanner_phone,
                to_number=owner_phone,
            )
            return Response({
                "success": True,
                "message": "Call initiated. You will be connected shortly.",
                "data": result,
            })
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"detail": "Failed to initiate call. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
