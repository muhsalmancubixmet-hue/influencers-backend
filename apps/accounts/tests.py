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
