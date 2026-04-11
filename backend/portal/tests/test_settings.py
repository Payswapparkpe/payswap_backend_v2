"""
Test settings override to handle allauth migration issues
"""
from django.test.utils import override_settings
from django.conf import settings

# Override settings for tests if needed
TEST_SETTINGS = {
    'ACCOUNT_LOGIN_METHODS': {'username', 'email'},
    'ACCOUNT_SIGNUP_FIELDS': ['email*', 'username*', 'password1*'],
}
