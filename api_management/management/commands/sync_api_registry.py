"""
Management command: sync API registry from URL configuration.
Creates APIRegistry rows for (version, method, endpoint) that don't exist, with status=OFF.
"""
from django.core.management.base import BaseCommand
from django.urls import get_resolver, URLPattern, URLResolver
from django.conf import settings

from api_management.models import APIRegistry, ServiceCategory


def _normalize_path(path: str) -> str:
    path = path.rstrip("/") or "/"
    if not path.startswith("/"):
        path = "/" + path
    return path


def _get_allowed_methods(view):
    """Return list of HTTP methods the view accepts."""
    if hasattr(view, "http_method_names"):
        return [m.upper() for m in view.http_method_names if m.upper() != "OPTIONS"]
    if hasattr(view, "allowed_methods"):
        return list(view.allowed_methods)
    if hasattr(view, "actions"):
        # ViewSet: map actions to methods
        return ["GET", "POST", "PUT", "PATCH", "DELETE"]
    return ["GET", "POST", "PUT", "PATCH", "DELETE"]


def _collect_api_routes(resolver, prefix=""):
    """Recursively collect (path, view) for all routes under prefix (e.g. api/)."""
    out = []
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            if hasattr(pattern.pattern, "_route"):
                part = pattern.pattern._route.strip("/")
            else:
                part = str(pattern.pattern).strip("^$").replace("\\", "").strip("/")
            new_prefix = f"{prefix}/{part}".strip("/") if part else prefix
            out.extend(_collect_api_routes(pattern, new_prefix))
        elif isinstance(pattern, URLPattern):
            if hasattr(pattern.pattern, "_route"):
                part = pattern.pattern._route.strip("/")
            else:
                part = str(pattern.pattern).strip("^$").replace("\\", "").strip("/")
            full = f"{prefix}/{part}".strip("/") if part else prefix
            callback = pattern.callback
            if hasattr(callback, "view_class"):
                callback = callback.view_class
            if callback and (callable(callback) or hasattr(callback, "as_view")):
                out.append((full, callback))
    return out


class Command(BaseCommand):
    help = "Sync APIRegistry from URL config: create missing (version, method, endpoint) with status=OFF."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be created, do not write DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        root = get_resolver()
        api_prefix = "api"
        api_resolver = None
        for pattern in root.url_patterns:
            if isinstance(pattern, URLResolver):
                route = getattr(pattern.pattern, "_route", None) or getattr(
                    pattern.pattern, "pattern", ""
                )
                if route and route.rstrip("/") == api_prefix:
                    api_resolver = pattern
                    break
        if not api_resolver:
            try:
                api_resolver = get_resolver("api.urls")
            except Exception:
                self.stdout.write("Could not find api/ URL include.")
                return

        routes = _collect_api_routes(api_resolver, api_prefix)
        # Build full path with /api/ prefix
        seen = set()
        created = 0
        default_category = None
        if not dry_run:
            default_category, _ = ServiceCategory.objects.get_or_create(
                code="general",
                defaults={"name": "General", "description": "Uncategorized APIs", "status": "active"},
            )

        for path, view in routes:
            full_path = _normalize_path("/" + path)
            if not full_path.startswith("/api/"):
                continue
            version = "v1"
            if "/api/v2/" in full_path or full_path.startswith("/api/v2"):
                version = "v2"
            elif "/api/v1/" in full_path or full_path.startswith("/api/v1"):
                version = "v1"

            methods = _get_allowed_methods(view)
            module_name = getattr(view, "__module__", "api").split(".")[-1]
            api_name = getattr(view, "__name__", view.__class__.__name__)

            for method in methods:
                if method == "OPTIONS":
                    continue
                key = (version, method, full_path)
                if key in seen:
                    continue
                seen.add(key)

                if dry_run:
                    self.stdout.write(f"Would create: {method} {full_path} ({version})")
                    created += 1
                    continue

                _, created_this = APIRegistry.objects.get_or_create(
                    version=version,
                    http_method=method,
                    endpoint=full_path,
                    defaults={
                        "service_category": default_category,
                        "module_name": module_name,
                        "api_name": api_name,
                        "status": APIRegistry.STATUS_OFF,
                    },
                )
                if created_this:
                    created += 1
                    self.stdout.write(f"Created: {method} {full_path} ({version})")

        self.stdout.write(self.style.SUCCESS(f"Sync complete. Created: {created}"))
