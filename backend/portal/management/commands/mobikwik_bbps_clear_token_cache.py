"""
Clear Mobikwik BBPS token from Django cache so the next BBPS request will fetch a new token.
Use after the 24h token limit resets so the app uses one fresh token instead of hitting the API repeatedly.
"""
from django.core.cache import cache
from django.core.management.base import BaseCommand

from portal.services.vendors.mobikwik import MOBIKWIK_BBPS_TOKEN_CACHE_KEY


class Command(BaseCommand):
    help = "Clear Mobikwik BBPS token cache so next request generates a new token (useful after 24h limit reset)."

    def handle(self, *args, **options):
        try:
            cache.delete(MOBIKWIK_BBPS_TOKEN_CACHE_KEY)
            self.stdout.write(self.style.SUCCESS("Mobikwik BBPS token cache cleared. Next BBPS request will get a new token."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to clear cache: {e}"))
