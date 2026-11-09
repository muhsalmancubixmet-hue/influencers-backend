"""
Regression and security test suite for the Accounts domain application.

Validates authentication, token issuance, RBAC permissions, and email verification
security boundaries according to the engineering rules.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
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

