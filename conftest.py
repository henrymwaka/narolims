import pytest

@pytest.fixture(autouse=True)
def _disable_security_redirects(settings):
    # Prevent SecurityMiddleware from forcing https://testserver/...
    settings.SECURE_SSL_REDIRECT = False

    # Prevent “secure cookie” behavior from interfering with session auth in tests
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False

    # Optional, but keeps security headers from confusing anything in tests
    settings.SECURE_HSTS_SECONDS = 0
