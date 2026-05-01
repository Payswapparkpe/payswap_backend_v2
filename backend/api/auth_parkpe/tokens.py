"""
ParkPe JWT tokens with role and scope claims on the access token (for DRF permission checks).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from portal.models import User
from portal.models.parking import ParkingOperator


def enrich_access_token_for_user(access_token, user: User) -> None:
    """Mutates SimpleJWT access token payload before encoding."""
    rc = str(getattr(user, "role_code", "") or "").strip().lower()
    access_token["role_code"] = rc or "customer"

    loc_ids = list(
        ParkingOperator.objects.filter(user=user, is_active=True).values_list("location_id", flat=True)
    )
    if loc_ids:
        access_token["parking_location_ids"] = loc_ids

    if rc.startswith("fleet_"):
        access_token["fleet_role"] = rc


class ParkPeRefreshToken(RefreshToken):
    """Refresh token that issues ParkPe-enriched access tokens."""

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        enrich_access_token_for_user(token.access_token, user)
        return token


class ParkPeTokenRefreshSerializer(TokenRefreshSerializer):
    """Re-embed role/scope on each refresh (matches TokenRefreshSerializer + enrichment)."""

    token_class = ParkPeRefreshToken

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM, None)
        user = None
        if user_id:
            user = get_user_model().objects.get(**{api_settings.USER_ID_FIELD: user_id})
            if not api_settings.USER_AUTHENTICATION_RULE(user):
                raise AuthenticationFailed(
                    self.error_messages["no_active_account"],
                    "no_active_account",
                )

        access = refresh.access_token
        if user is not None:
            enrich_access_token_for_user(access, user)

        data = {"access": str(access)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            refresh.outstand()

            data["refresh"] = str(refresh)

        return data
