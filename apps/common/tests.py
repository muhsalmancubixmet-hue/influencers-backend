"""
Unit and regression test suite for Common application components,
specifically Channels WebSocket JWT authentication and Origin security (REQ-WS-02).
"""

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import UserRole
from apps.common.ws_auth import (
    JwtAuthMiddleware,
    is_origin_allowed,
    extract_token_and_subprotocol,
)

User = get_user_model()


class WebSocketSecurityAndAuthTests(TestCase):
    """
    Test suite validating WebSocket JWT subprotocol parsing,
    Origin whitelisting, and secure subprotocol selection (REQ-WS-02, ADR-001).
    """

    def setUp(self) -> None:
        """
        Create active test user for JWT generation.

        :return: None
        """
        self.user = User.objects.create_user(
            username='ws_auth_testuser',
            email='ws_auth@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR,
            is_active=True
        )
        self.access_token = str(AccessToken.for_user(self.user))

    def test_is_origin_allowed_whitelisted(self) -> None:
        """
        Ensure origins in CORS_ALLOWED_ORIGINS are accepted.

        :return: None
        """
        with override_settings(CORS_ALLOWED_ORIGINS=['http://localhost:8080', 'http://localhost:8083']):
            self.assertTrue(is_origin_allowed('http://localhost:8080'))
            self.assertTrue(is_origin_allowed('http://localhost:8083/'))
            self.assertTrue(is_origin_allowed(''))  # Direct test/server origin

    def test_is_origin_allowed_rejected(self) -> None:
        """
        Ensure origins NOT in CORS_ALLOWED_ORIGINS are rejected.

        :return: None
        """
        with override_settings(CORS_ALLOWED_ORIGINS=['http://localhost:8080'], DEBUG=False):
            self.assertFalse(is_origin_allowed('http://evil-attacker.com'))
            self.assertFalse(is_origin_allowed('https://phishing-site.org'))

    def test_extract_token_from_subprotocols_list(self) -> None:
        """
        Verify that Sec-WebSocket-Protocol ['bearer', '<jwt>'] extracts token and selects 'bearer'.
        Never echoes raw token back.

        :return: None
        """
        scope = {
            'subprotocols': ['bearer', self.access_token],
            'headers': [],
            'query_string': b''
        }
        token, subprotocol = extract_token_and_subprotocol(scope)
        self.assertEqual(token, self.access_token)
        self.assertEqual(subprotocol, 'bearer')

    def test_extract_token_from_header(self) -> None:
        """
        Verify token extraction when subprotocols are passed via raw sec-websocket-protocol header.

        :return: None
        """
        header_val = f"bearer, {self.access_token}".encode('utf-8')
        scope = {
            'subprotocols': [],
            'headers': [(b'sec-websocket-protocol', header_val)],
            'query_string': b''
        }
        token, subprotocol = extract_token_and_subprotocol(scope)
        self.assertEqual(token, self.access_token)
        self.assertEqual(subprotocol, 'bearer')

    def test_extract_token_fallback_query_string(self) -> None:
        """
        Verify backward-compatible fallback for legacy ?token=<jwt> connections.
        No subprotocol should be returned.

        :return: None
        """
        scope = {
            'subprotocols': [],
            'headers': [],
            'query_string': f"token={self.access_token}".encode('utf-8')
        }
        token, subprotocol = extract_token_and_subprotocol(scope)
        self.assertEqual(token, self.access_token)
        self.assertIsNone(subprotocol)

    def test_jwt_auth_middleware_subprotocol_handshake_success(self) -> None:
        """
        Verify full ASGI middleware execution authenticating user and attaching 'bearer' subprotocol.

        :return: None
        """
        scope = {
            'type': 'websocket',
            'subprotocols': ['bearer', self.access_token],
            'headers': [(b'origin', b'http://localhost:8080')],
            'query_string': b''
        }

        async def inner_app(sc, recv, snd):
            return sc

        middleware = JwtAuthMiddleware(inner_app)
        resulting_scope = async_to_sync(middleware)(scope, None, None)

        self.assertFalse(resulting_scope.get('origin_rejected'))
        self.assertTrue(resulting_scope['user'].is_authenticated)
        self.assertEqual(resulting_scope['user'], self.user)
        self.assertEqual(resulting_scope.get('subprotocol'), 'bearer')

    def test_jwt_auth_middleware_origin_rejection(self) -> None:
        """
        Verify that disallowed origins are flagged with origin_rejected=True and user is anonymous.

        :return: None
        """
        with override_settings(CORS_ALLOWED_ORIGINS=['http://localhost:8080'], DEBUG=False):
            scope = {
                'type': 'websocket',
                'subprotocols': ['bearer', self.access_token],
                'headers': [(b'origin', b'http://untrusted-source.com')],
                'query_string': b''
            }

            async def inner_app(sc, recv, snd):
                return sc

            middleware = JwtAuthMiddleware(inner_app)
            resulting_scope = async_to_sync(middleware)(scope, None, None)

            self.assertTrue(resulting_scope.get('origin_rejected'))
            self.assertFalse(resulting_scope['user'].is_authenticated)


class UserNotificationServiceTests(TestCase):
    """
    Test suite validating dedicated create_user_notification helper
    and feed boundary isolation (REQ-NOTIF-01).
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='notif_target',
            email='target@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR,
            is_active=True
        )
        self.other_user = User.objects.create_user(
            username='other_target',
            email='other@example.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS,
            is_active=True
        )

    def test_create_user_notification_success(self) -> None:
        """
        Verify that create_user_notification creates a SENT, unread notification
        with expected attributes linked to the target user.
        """
        from apps.common.api.v1.services import create_user_notification
        from apps.common.models import NotificationKind, NotificationStatus

        notif = create_user_notification(
            recipient=self.user,
            title='Campaign Proposal Received',
            message='A brand has submitted a proposal for your review.',
            kind=NotificationKind.CAMPAIGN
        )

        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.recipient, self.user)
        self.assertEqual(notif.title, 'Campaign Proposal Received')
        self.assertEqual(notif.message, 'A brand has submitted a proposal for your review.')
        self.assertEqual(notif.kind, NotificationKind.CAMPAIGN)
        self.assertEqual(notif.status, NotificationStatus.SENT)
        self.assertFalse(notif.is_read)

    def test_create_user_notification_validation_errors(self) -> None:
        """
        Verify that blank title, blank message, or inactive/missing recipient
        raises ValidationError.
        """
        from django.core.exceptions import ValidationError
        from apps.common.api.v1.services import create_user_notification

        # Missing title
        with self.assertRaises(ValidationError):
            create_user_notification(recipient=self.user, title='  ', message='Body')

        # Missing message
        with self.assertRaises(ValidationError):
            create_user_notification(recipient=self.user, title='Title', message='  ')

        # None recipient
        with self.assertRaises(ValidationError):
            create_user_notification(recipient=None, title='Title', message='Body')

        # Inactive recipient
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(ValidationError):
            create_user_notification(recipient=self.user, title='Title', message='Body')


class NotificationTriggerEventTests(TestCase):
    """
    Test suite validating automated notification triggers across
    campaigns, inquiries, and creator verifications (REQ-NOTIF-02).
    """

    def setUp(self) -> None:
        from apps.creators.models import CreatorProfile
        from apps.businesses.models import BusinessProfile
        from apps.campaigns.models import Campaign, CampaignStatus, Inquiry
        from apps.common.models import Notification

        # Creator User & Profile
        self.creator_user = User.objects.create_user(
            username='trig_creator',
            email='trig_creator@test.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR,
            is_active=True
        )
        self.creator = CreatorProfile.objects.create(
            user=self.creator_user,
            handle='trigcreator',
            display_name='Trig Creator'
        )

        # Business User & Profile
        self.business_user = User.objects.create_user(
            username='trig_brand',
            email='trig_brand@test.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS,
            is_active=True
        )
        self.business = BusinessProfile.objects.create(
            user=self.business_user,
            company_name='Trigger Brands Inc'
        )

        # Open Campaign
        self.campaign = Campaign.objects.create(
            business=self.business,
            title='Autumn Visual Campaign',
            status=CampaignStatus.PUBLISHED
        )

        # Active Collaboration Inquiry
        self.inquiry = Inquiry.objects.create(
            business=self.business,
            creator=self.creator,
            subject='Collab Brief'
        )

    def test_apply_to_campaign_triggers_business_notification(self) -> None:
        """
        Submitting a bid to an open campaign must trigger a CAMPAIGN notification
        addressed to the campaign business owner.
        """
        from apps.campaigns.api.v1.services import apply_to_campaign
        from apps.common.models import Notification, NotificationKind

        apply_to_campaign(
            campaign_id=str(self.campaign.id),
            creator=self.creator,
            proposed_fee_cents=45000,
            pitch_text='Creative concept'
        )

        notif = Notification.objects.filter(recipient=self.business_user).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.kind, NotificationKind.CAMPAIGN)
        self.assertIn('Autumn Visual Campaign', notif.title)
        self.assertIn('@trigcreator', notif.message)

    def test_send_inquiry_reply_triggers_counterparty_notification(self) -> None:
        """
        Sending a reply in an inquiry thread must notify the other party.
        """
        from apps.campaigns.api.v1.services import send_inquiry_reply
        from apps.common.models import Notification, NotificationKind

        # Creator replies -> Business should receive notification
        send_inquiry_reply(
            inquiry_id=str(self.inquiry.id),
            sender=self.creator_user,
            body='Here is my updated storyboard.'
        )

        notif = Notification.objects.filter(recipient=self.business_user).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.kind, NotificationKind.USER)
        self.assertIn('Collab Brief', notif.title)

    def test_moderate_creator_verification_triggers_creator_notification(self) -> None:
        """
        Moderating creator verification status must trigger a VERIFICATION notification
        addressed to the creator user.
        """
        from apps.creators.api.v1.services import moderate_creator
        from apps.creators.models import VerificationStatus
        from apps.common.models import Notification, NotificationKind

        moderate_creator(
            creator_id=str(self.creator.id),
            verification_status=VerificationStatus.VERIFIED
        )

        notif = Notification.objects.filter(recipient=self.creator_user).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.kind, NotificationKind.VERIFICATION)
        self.assertIn('Verification', notif.title)


class AdminMediaAssetApiTests(TestCase):
    """
    Test suite validating Admin Media Asset REST endpoints and RBAC moderation (REQ-ADM-01).
    """

    def setUp(self) -> None:
        from rest_framework.test import APIClient
        from apps.common.models import MediaAsset, MediaType, AuditLog
        from apps.accounts.models import RoleTemplate, StaffProfile, ModuleChoice

        self.client = APIClient()

        # Superadmin staff user
        self.admin = User.objects.create_superuser(
            username='media_admin',
            email='admin@influencers.com',
            password='AdminPassword#2026!'
        )

        # Creator uploader
        self.uploader = User.objects.create_user(
            username='media_uploader',
            email='uploader@creator.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR,
            is_active=True
        )

        # Seed test media assets
        self.asset_img = MediaAsset.objects.create(
            uploader=self.uploader,
            file_name='portfolio_hero.jpg',
            file_type=MediaType.IMAGE,
            file_size_bytes=1024 * 500,
            cdn_url='https://cdn.influencers.com/portfolio_hero.jpg',
            mime_type='image/jpeg'
        )

        self.asset_vid = MediaAsset.objects.create(
            uploader=self.uploader,
            file_name='brand_reels_showcase.mp4',
            file_type=MediaType.VIDEO,
            file_size_bytes=1024 * 1024 * 5,
            cdn_url='https://cdn.influencers.com/showcase.mp4',
            mime_type='video/mp4'
        )

    def test_anonymous_access_denied(self) -> None:
        """Unauthenticated requests to admin media endpoints must be rejected."""
        response = self.client.get('/api/v1/admin/media/')
        self.assertEqual(response.status_code, 401)

    def test_admin_list_media_assets_success(self) -> None:
        """Staff with MEDIA access must receive paginated list of media assets."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/media/')
        self.assertEqual(response.status_code, 200)

        results = response.data['results'] if 'results' in response.data else response.data
        self.assertTrue(len(results) >= 2)
        filenames = [r['file_name'] for r in results]
        self.assertIn('portfolio_hero.jpg', filenames)
        self.assertIn('brand_reels_showcase.mp4', filenames)

    def test_admin_filter_media_assets_by_type(self) -> None:
        """Filtering by ?type=IMAGE returns only image media assets."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/media/?type=IMAGE')
        self.assertEqual(response.status_code, 200)

        results = response.data['results'] if 'results' in response.data else response.data
        for item in results:
            self.assertEqual(item['file_type'], 'IMAGE')

    def test_admin_get_and_delete_media_asset(self) -> None:
        """Detail retrieval and soft-deletion must succeed with compliance audit log."""
        from apps.common.models import MediaAsset, AuditLog

        self.client.force_authenticate(user=self.admin)
        detail_url = f"/api/v1/admin/media/{self.asset_img.id}/"

        # GET detail
        res_get = self.client.get(detail_url)
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.data['file_name'], 'portfolio_hero.jpg')

        # DELETE asset
        res_del = self.client.delete(detail_url)
        self.assertEqual(res_del.status_code, 200)

        # Confirm soft-deleted
        self.asset_img.refresh_from_db()
        self.assertTrue(self.asset_img.is_deleted)

        # GET now returns 404
        res_get2 = self.client.get(detail_url)
        self.assertEqual(res_get2.status_code, 404)

        # Confirm audit log entry
        audit = AuditLog.objects.filter(entity='MediaAsset', entity_id=str(self.asset_img.id)).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, 'DELETE_MEDIA_ASSET')



