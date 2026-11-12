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


class CampaignBidSerializerRegressionTests(TestCase):
    """
    Regression test suite verifying CampaignBidSerializer field mapping
    (pitch vs pitch_text).
    """

    def test_campaign_bid_serializer_field_mapping(self) -> None:
        """
        Verify that CampaignBidSerializer can be instantiated and maps pitch to pitch_text.

        :return: None
        """
        from apps.campaigns.api.v1.serializers import CampaignBidSerializer
        serializer = CampaignBidSerializer()
        self.assertIn('pitch', serializer.fields)
        self.assertIn('pitch_text', serializer.fields)


class InquiryChatConsumerAccessTests(TestCase):
    """
    Unit test suite validating InquiryChatConsumer helper routines (REQ-WS-01).
    Verifies that creator profile relationships and photo URLs resolve correctly.
    """

    def setUp(self) -> None:
        """
        Seed database with creator, business, inquiry, and non-participant user.

        :return: None
        """
        from django.contrib.auth import get_user_model
        from apps.accounts.models import UserRole
        from apps.creators.models import CreatorProfile
        from apps.businesses.models import BusinessProfile
        from apps.campaigns.models import Inquiry

        User = get_user_model()

        # 1. Create Creator user and CreatorProfile
        self.creator_user = User.objects.create_user(
            username='chat_creator',
            email='chat.creator@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR
        )
        self.creator_profile = CreatorProfile.objects.create(
            user=self.creator_user,
            handle='chat_creator',
            display_name='Chat Creator',
            photo_url='https://cdn.influencers.com/avatars/creator1.png'
        )

        # 2. Create Business user and BusinessProfile
        self.business_user = User.objects.create_user(
            username='chat_brand',
            email='chat.brand@example.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.business_user,
            company_name='Acme Brand Inc',
            logo_url='https://cdn.influencers.com/logos/acme.png'
        )

        # 3. Create Collaboration Inquiry linking Business and Creator
        self.inquiry = Inquiry.objects.create(
            business=self.business_profile,
            creator=self.creator_profile,
            subject='Collaboration for Summer Launch'
        )

        # 4. Create Unrelated user
        self.other_user = User.objects.create_user(
            username='stranger_user',
            email='stranger@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR
        )

    def test_creator_participant_access_and_photo_url(self) -> None:
        """
        Verify that creator access check resolves user.creator_profile and returns photo_url.

        :return: None
        """
        from asgiref.sync import async_to_sync
        from apps.campaigns.consumers import verify_inquiry_access

        has_access, sender_info, err = async_to_sync(verify_inquiry_access)(
            str(self.inquiry.id),
            self.creator_user
        )

        self.assertTrue(has_access)
        self.assertEqual(sender_info.get('sender_role'), 'creator')
        self.assertEqual(sender_info.get('sender_name'), 'Chat Creator')
        self.assertEqual(sender_info.get('sender_avatar'), 'https://cdn.influencers.com/avatars/creator1.png')
        self.assertEqual(err, "")

    def test_business_participant_access(self) -> None:
        """
        Verify that brand access check resolves user.business_profile and returns logo_url.

        :return: None
        """
        from asgiref.sync import async_to_sync
        from apps.campaigns.consumers import verify_inquiry_access

        has_access, sender_info, err = async_to_sync(verify_inquiry_access)(
            str(self.inquiry.id),
            self.business_user
        )

        self.assertTrue(has_access)
        self.assertEqual(sender_info.get('sender_role'), 'business')
        self.assertEqual(sender_info.get('sender_name'), 'Acme Brand Inc')
        self.assertEqual(sender_info.get('sender_avatar'), 'https://cdn.influencers.com/logos/acme.png')
        self.assertEqual(err, "")

    def test_unrelated_user_access_denied(self) -> None:
        """
        Verify that non-participants are rejected with access denied.

        :return: None
        """
        from asgiref.sync import async_to_sync
        from apps.campaigns.consumers import verify_inquiry_access

        has_access, sender_info, err = async_to_sync(verify_inquiry_access)(
            str(self.inquiry.id),
            self.other_user
        )

        self.assertFalse(has_access)
        self.assertIn("You are not a participant", err)

    def test_persist_inquiry_message_with_creator_profile(self) -> None:
        """
        Verify that persist_inquiry_message correctly creates the message record and attaches photo_url.

        :return: None
        """
        from asgiref.sync import async_to_sync
        from apps.campaigns.consumers import persist_inquiry_message
        from apps.campaigns.models import InquiryMessage

        msg_data = async_to_sync(persist_inquiry_message)(
            str(self.inquiry.id),
            self.creator_user,
            body="Hello! I am excited to collaborate on this campaign."
        )

        self.assertEqual(msg_data.get('sender_role'), 'creator')
        self.assertEqual(msg_data.get('sender_name'), 'Chat Creator')
        self.assertEqual(msg_data.get('sender_avatar'), 'https://cdn.influencers.com/avatars/creator1.png')
        self.assertEqual(msg_data.get('body'), 'Hello! I am excited to collaborate on this campaign.')

        # Verify database record exists
        msg_record = InquiryMessage.objects.get(id=msg_data['id'])
        self.assertEqual(msg_record.sender, self.creator_user)
        self.assertEqual(msg_record.body, 'Hello! I am excited to collaborate on this campaign.')


class PublicInquiryAntiIDORSecurityTests(TestCase):
    """
    Test suite validating Anti-IDOR and Anti-Account Hijacking protections on public inquiries (REQ-SEC-03).
    """

    def setUp(self) -> None:
        """
        Create creator profile and a registered password-protected business account.

        :return: None
        """
        from django.contrib.auth import get_user_model
        from apps.accounts.models import UserRole
        from apps.creators.models import CreatorProfile
        from apps.businesses.models import BusinessProfile

        User = get_user_model()

        self.creator_user = User.objects.create_user(
            username='target_creator',
            email='target.creator@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR
        )
        self.creator = CreatorProfile.objects.create(
            user=self.creator_user,
            handle='targetcreator',
            display_name='Target Creator'
        )

        # Registered business user with usable password
        self.registered_business = User.objects.create_user(
            username='registered_brand_owner',
            email='owner@establishedbrand.com',
            password='RealSecurePassword123!',
            role=UserRole.BUSINESS
        )
        self.business_profile = BusinessProfile.objects.create(
            user=self.registered_business,
            company_name='Established Brand Co'
        )

    def test_anonymous_cannot_impersonate_registered_password_business(self) -> None:
        """
        Verify that an unauthenticated caller cannot submit an inquiry using an existing
        password-protected business email (anti-IDOR / anti-hijacking).

        :return: None
        """
        from django.core.exceptions import ValidationError
        from apps.campaigns.api.v1.services import create_public_inquiry

        payload = {
            'creator_handle': 'targetcreator',
            'client_email': 'owner@establishedbrand.com',
            'client_name': 'Attacker Impersonator',
            'company_name': 'Fake Name',
            'subject': 'Forged inquiry',
            'message': 'Attempting to inject inquiry into established brand account.'
        }

        with self.assertRaises(ValidationError) as ctx:
            create_public_inquiry(payload, request_user=None)

        self.assertIn("already exists. Please log in", str(ctx.exception))

    def test_authenticated_business_owner_can_submit_inquiry(self) -> None:
        """
        Verify that when authenticated as the registered business user, inquiry creation succeeds.

        :return: None
        """
        from apps.campaigns.api.v1.services import create_public_inquiry

        payload = {
            'creator_handle': 'targetcreator',
            'client_email': 'owner@establishedbrand.com',
            'client_name': 'Legitimate Owner',
            'company_name': 'Established Brand Co',
            'subject': 'Real Collaboration Brief',
            'message': 'Legitimate inquiry submitted while authenticated.'
        }

        inquiry = create_public_inquiry(payload, request_user=self.registered_business)
        self.assertIsNotNone(inquiry.id)
        self.assertEqual(inquiry.business.user, self.registered_business)

    def test_guest_inquiry_succeeds_and_reusable_safely(self) -> None:
        """
        Verify that genuine guest inquiries (with unused emails) create un-passworded accounts
        and can submit subsequent inquiries safely.

        :return: None
        """
        from apps.campaigns.api.v1.services import create_public_inquiry

        guest_payload = {
            'creator_handle': 'targetcreator',
            'client_email': 'visitor@freshstartup.io',
            'client_name': 'Startup Founder',
            'company_name': 'Fresh Startup',
            'subject': 'First Collaboration',
            'message': 'Guest inquiry from non-registered visitor.'
        }

        inquiry1 = create_public_inquiry(guest_payload, request_user=None)
        self.assertIsNotNone(inquiry1.id)
        self.assertFalse(inquiry1.business.user.has_usable_password())

        # Second inquiry from same guest email succeeds without login demand
        guest_payload['subject'] = 'Second Collaboration'
        inquiry2 = create_public_inquiry(guest_payload, request_user=None)
        self.assertIsNotNone(inquiry2.id)
        self.assertEqual(inquiry1.business, inquiry2.business)


class CampaignApplicationCounterTests(TestCase):
    """
    Test suite validating atomic F() expression counter increments
    for Campaign.applications_count (REQ-SEC-04).
    """

    def setUp(self) -> None:
        from django.contrib.auth import get_user_model
        from apps.accounts.models import UserRole
        from apps.creators.models import CreatorProfile
        from apps.businesses.models import BusinessProfile
        from apps.campaigns.models import Campaign, CampaignStatus

        User = get_user_model()

        self.business_user = User.objects.create_user(
            username='brand_corp',
            email='brand@corp.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS
        )
        self.business = BusinessProfile.objects.create(
            user=self.business_user,
            company_name='Brand Corp'
        )
        self.campaign = Campaign.objects.create(
            business=self.business,
            title='Summer Launch 2026',
            status=CampaignStatus.PUBLISHED,
            applications_count=0
        )

        # Creator 1
        self.user1 = User.objects.create_user(
            username='creator_one',
            email='c1@test.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR
        )
        self.creator1 = CreatorProfile.objects.create(
            user=self.user1,
            handle='creatorone',
            display_name='Creator One'
        )

        # Creator 2
        self.user2 = User.objects.create_user(
            username='creator_two',
            email='c2@test.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR
        )
        self.creator2 = CreatorProfile.objects.create(
            user=self.user2,
            handle='creatortwo',
            display_name='Creator Two'
        )

    def test_apply_to_campaign_increments_counter_atomically(self) -> None:
        """
        Verify that apply_to_campaign updates applications_count atomically using F() expression.
        """
        from apps.campaigns.api.v1.services import apply_to_campaign
        from apps.campaigns.models import Campaign

        self.assertEqual(self.campaign.applications_count, 0)

        # First creator applies
        bid1 = apply_to_campaign(
            campaign_id=str(self.campaign.id),
            creator=self.creator1,
            proposed_fee_cents=50000,
            pitch_text='Pitch one'
        )
        self.assertIsNotNone(bid1.id)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.applications_count, 1)

        # Second creator applies
        bid2 = apply_to_campaign(
            campaign_id=str(self.campaign.id),
            creator=self.creator2,
            proposed_fee_cents=60000,
            pitch_text='Pitch two'
        )
        self.assertIsNotNone(bid2.id)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.applications_count, 2)


