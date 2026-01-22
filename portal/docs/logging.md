# Logging Documentation

## Overview

Portal uses a secure logging system with automatic sensitive data sanitization and Celery task integration for asynchronous logging.

## Features

- **Secure Logging**: Automatic sanitization of sensitive data (passwords, tokens, API keys, etc.)
- **Structured Logs**: JSON-formatted logs for easy parsing and analysis
- **Asynchronous Logging**: Celery tasks for non-blocking log writes
- **User Action Tracking**: Automatic logging of user actions
- **API Call Logging**: Track external API calls with timing
- **Security Event Logging**: Special handling for security-related events

## Usage

### Basic Logging

```python
from portal.utils.logging_helper import get_logger

logger = get_logger('portal')

# Simple logging
logger.info("User logged in", user=request.user)
logger.error("Failed to process payment", user=request.user, extra_data={'amount': 1000})
```

### User Action Logging

```python
from portal.tasks.logging_tasks import log_user_action_task

# Asynchronous (recommended)
log_user_action_task.delay(
    action='create_user',
    user_id=user.id,
    resource='user',
    resource_id=str(new_user.id),
    status='success'
)

# Synchronous
logger.log_user_action(
    action='update_profile',
    user=request.user,
    resource='profile',
    resource_id=str(profile.id),
    status='success'
)
```

### API Call Logging

```python
from portal.tasks.logging_tasks import log_api_call_task

# Asynchronous
log_api_call_task.delay(
    service='kaleyra',
    endpoint='send_sms',
    method='POST',
    status_code=200,
    response_time=0.5,
    user_id=user.id if user.is_authenticated else None
)
```

### Security Event Logging

```python
from portal.tasks.logging_tasks import log_security_event_task

log_security_event_task.delay(
    event_type='failed_login',
    message='Multiple failed login attempts detected',
    user_id=user.id,
    severity='high',
    extra_data={'attempts': 5, 'ip_address': '192.168.1.1'}
)
```

### Using Decorators

```python
from portal.utils.logging_decorators import log_user_action_decorator, log_api_call_decorator

@log_user_action_decorator('create_user', resource='user')
def create_user_view(request, ...):
    # Function automatically logged
    ...

@log_api_call_decorator('kaleyra')
def send_otp(phone, otp):
    # API call automatically logged with timing
    ...
```

## Sensitive Data Sanitization

The logging system automatically masks:

- Passwords, tokens, API keys
- Credit card numbers, PAN, Aadhaar
- OTP codes, verification codes
- Encrypted data, seed phrases
- Any field matching sensitive patterns

## Log Format

Logs are structured as JSON:

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "level": "INFO",
  "message": "User action: create_user on user (ID: 123) - success",
  "service": "portal",
  "user": {
    "id": 1,
    "username": "A00123456",
    "role": "admin"
  },
  "data": {
    "action": "create_user",
    "resource": "user",
    "resource_id": "123",
    "status": "success"
  },
  "request_id": "req-abc123"
}
```

## Log Files

- `logs/portal.log`: All portal logs
- `logs/portal_errors.log`: Error and critical logs only

## Celery Tasks

All logging tasks are available as Celery tasks:

- `portal.tasks.log_user_action`
- `portal.tasks.log_api_call`
- `portal.tasks.log_security_event`
- `portal.tasks.log_generic`
- `portal.tasks.batch_log_cleanup`

## Best Practices

1. **Use async logging for non-critical paths**: Use Celery tasks to avoid blocking
2. **Include request_id for tracing**: Pass request IDs to correlate logs
3. **Log security events immediately**: Use synchronous logging for critical security events
4. **Sanitize before logging**: The system does this automatically, but be mindful
5. **Use appropriate log levels**: DEBUG for development, INFO for normal operations, ERROR for failures
