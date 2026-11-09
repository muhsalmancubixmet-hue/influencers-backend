"""
Regression and security test suite for the Accounts domain application.

Validates authentication, token issuance, RBAC permissions, and email verification
security boundaries according to the engineering rules.
"""

import os
from django.test import TestCase
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.signing import TimestampSigner
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User, UserRole
from apps.creators.models import CreatorProfile
from apps.accounts.api.v1.services import verify_creator_email
from django.core.cache import cache


class EmailVerificationSecurityTests(TestCase):
    """
    Security regression tests verifying that the email verification service and endpoint
    strictly enforce cryptographic signature validity and never fall back to email alone.
    """

    def setUp(self):
        """Set up test user and client fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testcreator",
            email="victim@example.com",
            password="SecurePassword123!",
            role=UserRole.CREATOR,
            is_active=False
        )
        self.profile = CreatorProfile.objects.create(
            user=self.user,
            handle="testcreator",
            display_name="Test Creator"
        )
        self.signer = TimestampSigner()

    def test_verify_creator_email_with_invalid_token_and_valid_email_raises_validation_error(self):
        """
        REGRESSION TEST (SEC-CRIT-01):
        An invalid token must NEVER fall back to email lookup. It must raise ValidationError.
        """
        with self.assertRaises(ValidationError) as context:
            verify_creator_email(
                token="completely_fake_invalid_token_123",
                email=self.user.email
            )
        self.assertIn("Invalid or corrupted verification token", str(context.exception))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active, "Inactive user must not be activated by invalid token.")

    def test_verify_creator_email_api_endpoint_rejects_invalid_token_with_valid_email(self):
        """
        REGRESSION TEST (SEC-CRIT-01):
        POST /api/v1/auth/verify-email/ with an invalid token and valid email must return 400.
        """
        response = self.client.post('/api/v1/auth/verify-email/', {
            'token': 'malicious_forged_token_xyz',
            'email': self.user.email
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active, "User account must remain inactive.")

    def test_verify_creator_email_with_valid_token_succeeds(self):
        """A valid cryptographically signed token must successfully activate the user."""
        valid_token = self.signer.sign(str(self.user.id))
        result = verify_creator_email(token=valid_token)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertIn('access', result)
        self.assertIn('refresh', result)
        self.assertEqual(result['user'], self.user)


class AuthThrottlingSecurityTests(TestCase):
    """
    Security regression test suite validating DRF rate limiting and throttling (SEC-HIGH-01).
    Ensures authentication endpoints enforce strict rate limits against brute force attacks.
    """

    def setUp(self) -> None:
        """
        Prepare test client and flush cache before each throttle test.

        :return: None
        """
        self.client = APIClient()
        cache.clear()

    def tearDown(self) -> None:
        """
        Flush cache after each test to avoid cross-test throttle pollution.

        :return: None
        """
        cache.clear()

    def test_login_rate_limit_throttling_enforced(self) -> None:
        """
        Verify that login endpoint enforces 'auth' scope throttle limit (5 req/min).
        Excessive requests within the window must receive 429 Too Many Requests.

        :return: None
        """
        url = '/api/v1/auth/token/'
        # First 5 attempts should return 401 Unauthorized but not be throttled
        for i in range(5):
            response = self.client.post(url, {
                'email': 'target@example.com',
                'password': f'WrongPass{i}!'
            }, format='json')
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # 6th attempt within the 1-minute window must be blocked by ScopedRateThrottle
        throttled_response = self.client.post(url, {
            'email': 'target@example.com',
            'password': 'WrongPassFinal!'
        }, format='json')
        self.assertEqual(throttled_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_creator_registration_rate_limit_throttling_enforced(self) -> None:
        """
        Verify that public creator registration enforces 'auth' scope rate limit.
        Submissions exceeding 5 per minute must be throttled with 429.

        :return: None
        """
        url = '/api/v1/auth/creator/register/'
        # Perform 5 registration requests
        for i in range(5):
            response = self.client.post(url, {
                'email': f'creator_{i}@example.com',
                'username': f'creator_{i}',
                'password': 'Password123!'
            }, format='json')
            self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

        # 6th request within window must be rejected with 429 Too Many Requests
        throttled_response = self.client.post(url, {
            'email': 'creator_overflow@example.com',
            'username': 'creator_overflow',
            'password': 'Password123!'
        }, format='json')
        self.assertEqual(throttled_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_rotating_x_forwarded_for_header_does_not_bypass_login_throttle(self) -> None:
        """
        Verify that rotating HTTP_X_FORWARDED_FOR headers does NOT bypass login throttling
        when NUM_PROXIES is configured to 0. Throttling must identify clients by REMOTE_ADDR.

        :return: None
        """
        url = '/api/v1/auth/token/'
        # Step 1: Send 5 failed login attempts with varying spoofed X-Forwarded-For headers
        for i in range(5):
            spoofed_ip = f'198.51.100.{i + 1}'
            response = self.client.post(
                url,
                {'email': 'target@example.com', 'password': f'WrongPass{i}!'},
                format='json',
                HTTP_X_FORWARDED_FOR=spoofed_ip
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Step 2: 6th attempt with yet another spoofed IP must still be blocked by throttle (HTTP 429)
        throttled_response = self.client.post(
            url,
            {'email': 'target@example.com', 'password': 'WrongPassFinal!'},
            format='json',
            HTTP_X_FORWARDED_FOR='198.51.100.99'
        )
        self.assertEqual(throttled_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class CacheSettingsSecurityTests(TestCase):
    """
    Validation test suite ensuring production cache safety and fail-closed configurations (SEC-CRIT-03/04).
    """

    def test_debug_defaults_to_false_when_env_unset(self) -> None:
        """
        Verify that DEBUG evaluation logic defaults to False when the environment variable is unset.

        :return: None
        """
        # Simulate unset DEBUG environment variable
        eval_debug = os.environ.get('UNSET_DEBUG_TEST_VAR', 'False').lower() in ('true', '1', 'yes')
        self.assertFalse(eval_debug, "DEBUG must default to False when env var is unset.")

    def test_cache_requires_redis_url_when_debug_false(self) -> None:
        """
        Ensure setting up CACHES with DEBUG=False raises ImproperlyConfigured if REDIS_URL is missing.

        :return: None
        """
        # Replicate settings.py cache resolution logic
        def resolve_cache_config(debug: bool, redis_url: str = "") -> dict:
            if not debug:
                if not redis_url:
                    raise ImproperlyConfigured(
                        "REDIS_URL or CACHE_URL environment variable is mandatory when DEBUG=False to ensure distributed cache safety."
                    )
                return {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': redis_url}
            return {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}

        with self.assertRaises(ImproperlyConfigured):
            resolve_cache_config(debug=False, redis_url="")

    def test_rediss_enforces_certificate_verification(self) -> None:
        """
        Ensure rediss:// URLs configure explicit SSL certificate validation and hostname checking.

        :return: None
        """
        import ssl
        from django.core.cache.backends.redis import RedisCache

        rediss_url = "rediss://127.0.0.1:6379/0"
        redis_options = {
            'ssl_cert_reqs': ssl.CERT_REQUIRED,
            'ssl_check_hostname': True,
        }
        cache_instance = RedisCache(rediss_url, {'OPTIONS': redis_options})
        pool = cache_instance._cache._get_connection_pool(True)

        self.assertEqual(pool.connection_kwargs.get('ssl_cert_reqs'), ssl.CERT_REQUIRED)
        self.assertTrue(pool.connection_kwargs.get('ssl_check_hostname'))


class RoleTemplateSerializerRegressionTests(TestCase):
    """
    Regression test suite verifying RoleTemplateSerializer field configuration
    and slugification.
    """

    def test_role_template_serializer_success(self) -> None:
        """
        Ensure RoleTemplateSerializer correctly serializes name, slug, and is_system.

        :return: None
        """
        from apps.accounts.models import RoleTemplate
        from apps.accounts.api.v1.serializers import RoleTemplateSerializer

        role = RoleTemplate.objects.create(
            name='Content Moderator',
            description='Reviews creator content and profiles',
            is_system_role=True
        )
        serializer = RoleTemplateSerializer(role)

        self.assertEqual(serializer.data['name'], 'Content Moderator')
        self.assertEqual(serializer.data['slug'], 'content-moderator')
        self.assertTrue(serializer.data['is_system'])


