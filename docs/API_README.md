# API Versioning Guide

## Overview

The Payswap API uses versioning to separate internal and external access:

- **v1**: Internal API (staff/authenticated users)
- **v2**: External API (public/partners)

## Access Control

### API v1 - Internal Access

**URL**: `/api/v1/`

**Authentication**: 
- Session Authentication
- Token Authentication
- Staff users have full access
- Authenticated users have access

**Permissions**: 
- `IsInternalUser`: Staff or authenticated users
- `IsStaffOnly`: Staff only (strict)

**Throttling**: 
- Authenticated: 1000/hour
- Anonymous: 100/hour

**Use Cases**:
- Admin operations
- Internal tools
- Staff dashboards
- Internal integrations

**Example**:
```bash
# Requires authentication
curl -H "Authorization: Token YOUR_TOKEN" \
     http://localhost:8000/api/v1/health/
```

### API v2 - External Parties

**URL**: `/api/v2/`

**Authentication**:
- Public endpoints (no auth)
- API Key authentication (for partners)
- Token authentication (optional)

**Permissions**:
- `AllowAny`: Public access
- `HasAPIKey`: Requires API key
- `IsExternalUser`: External access control

**Throttling**:
- Public: 100/hour
- Partner (with API key): 1000/hour

**Use Cases**:
- Public integrations
- Partner APIs
- External services
- Public documentation

**Example**:
```bash
# Public endpoint (no auth)
curl http://localhost:8000/api/v2/health/

# Partner endpoint (with API key)
curl -H "X-API-Key: YOUR_API_KEY" \
     http://localhost:8000/api/v2/partner/
```

## Endpoints

### v1 - Internal

- `GET /api/v1/health/` - Health check (requires auth)

### v2 - External

- `GET /api/v2/health/` - Health check (public)
- `GET /api/v2/public/` - Public endpoint
- `GET /api/v2/partner/` - Partner endpoint (requires API key)

## Adding New Endpoints

### Internal Endpoint (v1)

```python
# api/v1/views.py
from rest_framework import viewsets
from .permissions import IsInternalUser

class InternalViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInternalUser]
    # ... rest of your viewset
```

```python
# api/v1/urls.py
router.register(r'internal-resource', InternalViewSet, basename='internal')
```

### External Endpoint (v2)

```python
# api/v2/views.py
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from .permissions import HasAPIKey

class PublicView(APIView):
    permission_classes = [AllowAny]  # Public
    # ...

class PartnerView(APIView):
    permission_classes = [HasAPIKey]  # Requires API key
    # ...
```

```python
# api/v2/urls.py
urlpatterns = [
    path("public-endpoint/", PublicView.as_view()),
    path("partner-endpoint/", PartnerView.as_view()),
]
```

## Security Best Practices

1. **v1 (Internal)**:
   - Always require authentication
   - Use staff-only for sensitive operations
   - Log all access
   - Higher rate limits

2. **v2 (External)**:
   - Use API keys for partners
   - Implement rate limiting
   - Validate all inputs
   - Sanitize responses
   - Monitor usage

## API Documentation

- Swagger UI: `/api/schema/swagger-ui/`
- ReDoc: `/api/schema/redoc/`
- OpenAPI Schema: `/api/schema/`
