"""
Unit and regression test suite for Businesses domain application.

Validates business registration, password policy enforcement (REQ-SEC-05),
and profile operations according to SaaS security rules.
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.businesses.models import BusinessProfile

User = get_user_model()


class BusinessRegistrationPasswordValidationTests(TestCase):
    """
    Test suite validating Django password validation enforcement during
    business / brand self-registration (REQ-SEC-05).
    """

    def setUp(self) -> None:
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.register_url = '/api/v1/business/register/'

    def test_registration_rejects_common_weak_password(self) -> None:
        """
        Submitting a common password such as 'password' or '12345678' must be rejected
        with HTTP 400 Bad Request and descriptive validation errors.
        """
        payload = {
            'company_name': 'Acme Brands Inc',
            'email': 'acme.owner@example.com',
            'password': 'password',
            'business_type': 'E-commerce',
            'contact_name': 'Alice Smith',
            'contact_phone': '+91 9876543210'
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        errors = str(response.data['password'])
        self.assertTrue('common' in errors.lower() or 'short' in errors.lower() or 'entirely numeric' in errors.lower())
        self.assertFalse(User.objects.filter(email='acme.owner@example.com').exists())

    def test_registration_rejects_all_numeric_password(self) -> None:
        """
        Submitting an all-numeric password such as '1234567890' must be rejected.
        """
        payload = {
            'company_name': 'Acme Brands Inc',
            'email': 'acme.owner2@example.com',
            'password': '1234567890',
            'business_type': 'E-commerce',
            'contact_name': 'Alice Smith',
            'contact_phone': '+91 9876543210'
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        errors = str(response.data['password'])
        self.assertTrue('numeric' in errors.lower() or 'common' in errors.lower())
        self.assertFalse(User.objects.filter(email='acme.owner2@example.com').exists())

    def test_registration_accepts_strong_password(self) -> None:
        """
        Submitting a strong, non-trivial password must succeed with HTTP 200/201.
        """
        payload = {
            'company_name': 'Strong Security Corp',
            'email': 'brand@strongcorp.io',
            'password': 'Str0ng&Complex#Pass2026!',
            'business_type': 'Enterprise SaaS',
            'contact_name': 'Robert Strong',
            'contact_phone': '+91 9876543219'
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        user = User.objects.filter(email='brand@strongcorp.io').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.check_password('Str0ng&Complex#Pass2026!'))
        self.assertTrue(BusinessProfile.objects.filter(user=user).exists())

    def test_registration_triggers_welcome_email(self) -> None:
        """
        Verify that registering a new business dispatches a welcome email task.
        """
        from unittest.mock import patch
        payload = {
            'company_name': 'Horizon Brands',
            'email': 'contact@horizonbrands.test',
            'password': 'HorizonSecure#2026!',
            'business_type': 'Consumer Retail',
            'contact_name': 'Meera Nair',
            'contact_phone': '+91 9988776655'
        }
        with patch('apps.businesses.tasks.send_business_welcome_email_task.apply') as mock_apply, \
             patch('apps.businesses.tasks.send_business_welcome_email_task.delay') as mock_delay:
            response = self.client.post(self.register_url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertTrue(mock_apply.called or mock_delay.called)

    def test_business_inquiries_unread_count_endpoint(self) -> None:
        """
        Verify that GET /api/v1/business/inquiries/unread-count/ calculates unread messages.
        """
        from apps.accounts.models import UserRole
        from apps.campaigns.models import Inquiry, InquiryMessage
        from apps.creators.models import CreatorProfile

        user = User.objects.create_user(
            username='unread_test_biz',
            email='unread@biz.test',
            password='Password123!',
            role=UserRole.BUSINESS
        )
        profile = BusinessProfile.objects.create(
            user=user,
            company_name='Test Unread Brand',
            contact_email=user.email
        )
        creator_user = User.objects.create_user(
            username='creator_sender',
            email='creator@test.com',
            password='Password123!',
            role=UserRole.CREATOR
        )
        creator = CreatorProfile.objects.create(user=creator_user, handle='creator_sender')

        inquiry = Inquiry.objects.create(
            business=profile,
            creator=creator,
            subject='Campaign Inquiry 1'
        )
        # Message from creator (unread by brand)
        InquiryMessage.objects.create(
            inquiry=inquiry,
            sender=creator_user,
            body='Hello, here is my rate card.',
            is_read=False
        )
        # Message from brand (sent by me, not counted in unread)
        InquiryMessage.objects.create(
            inquiry=inquiry,
            sender=user,
            body='Thanks for connecting.',
            is_read=False
        )

        self.client.force_authenticate(user=user)
        res = self.client.get('/api/v1/business/inquiries/unread-count/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data.get('unread_count'), 1)

