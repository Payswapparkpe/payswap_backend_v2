# Internal Log Management System

## Overview

The Payswap project now includes a comprehensive internal log management system that captures all application actions, requests, and errors in the database for easy querying, analysis, and issue tracking.

## Features

### 1. **Database Storage**
- All logs are stored in the `LogEntry` model in the database
- Logs are also written to categorized files (existing behavior)
- Database storage enables easy querying and filtering

### 2. **Automatic Logging**
- **Request Logging Middleware**: Captures all HTTP requests automatically
  - Request method, URL, status code
  - Response time
  - Client IP, user agent, session ID
  - User information (if authenticated)
  - Query parameters
- **Action Logging**: All user actions are logged via existing logging tasks
- **Error Logging**: Exceptions and errors are automatically captured with full tracebacks

### 3. **Log Categories**
Logs are automatically categorized:
- **API**: API endpoint calls
- **Auth**: Authentication and authorization events
- **Payment**: Payment and wallet transactions
- **Notification**: SMS, email, OTP deliveries
- **Security**: Security events, failed logins, lockouts
- **General**: All other logs

### 4. **Log Levels**
- **DEBUG**: Detailed debugging information
- **INFO**: General informational messages
- **WARNING**: Warning messages (non-critical issues)
- **ERROR**: Error messages (issues that need attention)
- **CRITICAL**: Critical errors (system failures)

### 5. **Issue Tracking**
- **Resolution Status**: Logs can be marked as resolved/unresolved
- **Notes**: Add notes when resolving issues
- **Resolution Tracking**: Track who resolved what and when

## Access Points

### 1. **Web Interface** (Staff Only)
- **URL**: `/logs/`
- **Features**:
  - View all logs with filtering
  - Filter by level, category, status, user, date range
  - Search logs by message, module, URL, request ID
  - View detailed log entries
  - Mark logs as resolved/unresolved
  - Add resolution notes

### 2. **Django Admin**
- **URL**: `/admin/portal/logentry/`
- **Features**:
  - Full admin interface for log management
  - Advanced filtering and search
  - Bulk actions (mark resolved/unresolved)
  - Detailed log entry editing

### 3. **Admin Dashboard**
- Quick link to log management from admin dashboard

## Usage

### Viewing Logs

1. **Via Web Interface**:
   - Navigate to `/logs/` (requires staff permissions)
   - Use filters to find specific logs
   - Click on any log to see details

2. **Via Django Admin**:
   - Navigate to `/admin/portal/logentry/`
   - Use admin filters and search

### Filtering Logs

Available filters:
- **Log Level**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Category**: API, Auth, Payment, Notification, Security, General
- **Status**: Resolved, Unresolved, All
- **User**: Filter by specific user
- **Date Range**: Filter by timestamp
- **Search**: Search in message, module, URL, request ID

### Resolving Issues

1. Click on a log entry to view details
2. If it's an error or issue, add resolution notes
3. Click "Mark as Resolved"
4. The log will be marked as resolved with timestamp and resolver

## What Gets Logged

### Automatic Logging

1. **All HTTP Requests**:
   - Method, URL, status code
   - Response time
   - Client IP, user agent
   - User (if authenticated)
   - Query parameters

2. **User Actions**:
   - Login/logout
   - Profile updates
   - User creation
   - Permission changes
   - KYC submissions
   - Wallet transactions

3. **API Calls**:
   - External API calls (Kaleyra, Cashfree, etc.)
   - Response times
   - Status codes
   - Error responses

4. **Security Events**:
   - Failed login attempts
   - Account lockouts
   - Permission violations
   - Suspicious activities

5. **Errors & Exceptions**:
   - Full tracebacks
   - Exception types
   - Error messages
   - Request context

## Database Schema

### LogEntry Model

```python
- timestamp: DateTime (indexed)
- log_level: CharField (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- category: CharField (api, auth, payment, notification, security, general)
- message: TextField
- module_name: CharField (indexed)
- url: CharField (indexed)
- request_id: CharField (indexed)
- response_id: CharField
- user: ForeignKey to User (indexed)
- client_ip: GenericIPAddressField (indexed)
- user_agent: TextField
- session_id: CharField (indexed)
- extra_data: JSONField (sanitized)
- traceback: TextField (for errors)
- exception_type: CharField (for errors)
- resolved: BooleanField (indexed)
- resolved_at: DateTimeField
- resolved_by: ForeignKey to User
- notes: TextField
```

## Performance Considerations

- Logs are written asynchronously via Celery tasks (non-blocking)
- Database indexes on frequently queried fields
- Automatic log file rotation (existing behavior)
- Consider archiving old logs periodically

## Best Practices

1. **Regular Review**: Check unresolved ERROR and CRITICAL logs regularly
2. **Resolution Notes**: Always add notes when resolving issues
3. **Filtering**: Use filters to focus on specific issues
4. **Search**: Use search to find related logs by request ID or user
5. **Archiving**: Consider archiving old resolved logs periodically

## Troubleshooting

### No Logs Appearing

1. Check if Celery worker is running (logs are written asynchronously)
2. Check database connection
3. Verify middleware is enabled in settings
4. Check for any errors in server logs

### Performance Issues

1. Consider adding database indexes if needed
2. Archive old logs periodically
3. Use filters to reduce query size
4. Consider pagination for large result sets

## API Access

Logs can also be accessed programmatically:

```python
from portal.models import LogEntry
from django.utils import timezone
from datetime import timedelta

# Get recent errors
recent_errors = LogEntry.objects.filter(
    log_level='ERROR',
    timestamp__gte=timezone.now() - timedelta(hours=24),
    resolved=False
)

# Get logs for a specific user
user_logs = LogEntry.objects.filter(user=user)

# Get logs for a specific request
request_logs = LogEntry.objects.filter(request_id=request_id)
```

## Security

- Only staff users can view logs
- Sensitive data is automatically sanitized before logging
- Passwords, tokens, API keys are masked
- Personal information (PAN, Aadhaar) is redacted
