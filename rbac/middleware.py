"""
Middleware to set Hub context from request headers.
Angular (or other clients) can send X-Project-Code and X-Department-Code to scope permission checks.
"""


class HubContextMiddleware:
    """
    Read X-Project-Code and X-Department-Code from request headers and set
    request.hub_project_code and request.hub_department_code for permission layer.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.hub_project_code = (
            request.META.get("HTTP_X_PROJECT_CODE") or ""
        ).strip().lower() or None
        request.hub_department_code = (
            request.META.get("HTTP_X_DEPARTMENT_CODE") or ""
        ).strip().lower() or None
        return self.get_response(request)
