"""
Unit and regression test suite for Campaigns domain application.

Validates campaign and inquiry rate limits, access control boundaries, and
service interactions per SaaS engineering architecture standards.
"""

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class PublicInquiryRateLimitSecurityTests(TestCase):
    """
    Security regression test suite validating DRF rate limiting on public inquiry endpoints (SEC-HIGH-01).
    Ensures public lead and collaboration inquiry endpoints enforce rate limits.
    """

    def setUp(self) -> None:
        """
        Prepare API test client and flush cache before each test run.

        :return: None
        """
        self.client = APIClient()
        cache.clear()

    def tearDown(self) -> None:
        """
        Flush cache after test execution to prevent cross-test throttle pollution.

        :return: None
        """
        cache.clear()

    def test_public_inquiry_rate_limit_throttling_enforced(self) -> None:
        """
        Verify that POST /api/v1/public/inquiries/ enforces the 'inquiry' throttle rate (10/min).
        The 11th request within the time window must be throttled with 429 Too Many Requests.

        :return: None
        """
        url = '/api/v1/public/inquiries/'
        payload = {
            'creator_id': '00000000-0000-0000-0000-000000000000',
            'business_name': 'Acme Corp',
            'contact_email': 'contact@acme.com',
            'message': 'Hello from automated rate limit tester.'
        }

        # First 10 requests are processed (likely 400 Bad Request due to mock creator_id, but NOT throttled)
        for _ in range(10):
            response = self.client.post(url, payload, format='json')
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # 11th request exceeds the 10/minute inquiry rate and must return 429
        throttled_response = self.client.post(url, payload, format='json')
        self.assertEqual(throttled_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
