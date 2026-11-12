import io
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.creators.models import CreatorProfile

User = get_user_model()


def generate_test_image_bytes(image_format: str = 'PNG') -> bytes:
    """
    Generate minimal valid image byte content for testing image uploads.

    :param image_format: Valid Pillow image format string (e.g. 'PNG', 'JPEG').
    :return: Bytes of generated image.
    """
    buf = io.BytesIO()
    image = Image.new('RGB', (10, 10), color='blue')
    image.save(buf, format=image_format)
    buf.seek(0)
    return buf.getvalue()


class CreatorMediaUploadSecurityTests(APITestCase):
    """
    Test suite validating upload security constraints (SEC-CRIT-04).
    Enforces extension whitelist, file size limit, and image structure verification.
    """

    def setUp(self) -> None:
        """
        Seed database with authenticated creator user and profile.

        :return: None
        """
        # Step 1: Create creator user
        self.creator_user = User.objects.create_user(
            username='creator_upload_user',
            email='creator.upload@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR
        )
        # Step 2: Create associated CreatorProfile
        self.creator_profile = CreatorProfile.objects.create(
            user=self.creator_user,
            handle='upload_creator',
            display_name='Upload Creator'
        )
        # Step 3: Determine media upload endpoint URL
        self.upload_url = reverse('creator_media_upload')

    def test_valid_image_upload_success(self) -> None:
        """
        Ensure authentic image file with whitelisted extension (.png) is accepted.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        image_content = generate_test_image_bytes('PNG')
        uploaded_file = SimpleUploadedFile(
            name='avatar.png',
            content=image_content,
            content_type='image/png'
        )

        response = self.client.post(
            self.upload_url,
            {'file': uploaded_file, 'file_type': 'AVATAR'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('url', response.data)
        self.assertEqual(response.data['file_name'], 'avatar.png')

    def test_oversized_file_rejected(self) -> None:
        """
        Ensure file exceeding 10MB limit is rejected with 400 Bad Request.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        # 10 MB + 1 byte payload
        oversized_content = b'0' * (10 * 1024 * 1024 + 1)
        oversized_file = SimpleUploadedFile(
            name='large_asset.png',
            content=oversized_content,
            content_type='image/png'
        )

        response = self.client.post(
            self.upload_url,
            {'file': oversized_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File size exceeds maximum allowed limit', response.data.get('detail', ''))

    def test_svg_file_strictly_blocked(self) -> None:
        """
        Ensure SVG vector uploads are blocked to prevent Stored XSS attacks.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        svg_file = SimpleUploadedFile(
            name='vector_payload.svg',
            content=svg_content,
            content_type='image/svg+xml'
        )

        response = self.client.post(
            self.upload_url,
            {'file': svg_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not permitted', response.data.get('detail', ''))

    def test_html_file_strictly_blocked(self) -> None:
        """
        Ensure HTML file uploads are blocked to prevent client script execution.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        html_content = b'<!DOCTYPE html><html><body><script>alert("xss")</script></body></html>'
        html_file = SimpleUploadedFile(
            name='index.html',
            content=html_content,
            content_type='text/html'
        )

        response = self.client.post(
            self.upload_url,
            {'file': html_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not permitted', response.data.get('detail', ''))

    def test_disallowed_extension_rejected(self) -> None:
        """
        Ensure executable/script files (.exe, .sh, etc.) outside whitelist are rejected.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        payload = SimpleUploadedFile(
            name='malicious.exe',
            content=b'MZBINARYCONTENT',
            content_type='application/x-msdownload'
        )

        response = self.client.post(
            self.upload_url,
            {'file': payload},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not permitted', response.data.get('detail', ''))

    def test_fake_image_rejected_by_pillow(self) -> None:
        """
        Ensure file disguised with .png extension but invalid image bytes is rejected by Pillow.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        fake_image = SimpleUploadedFile(
            name='fake_photo.png',
            content=b'THIS_IS_NOT_A_REAL_PNG_IMAGE_FILE',
            content_type='image/png'
        )

        response = self.client.post(
            self.upload_url,
            {'file': fake_image},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid or corrupted image content', response.data.get('detail', ''))

    def test_valid_pdf_document_upload_success(self) -> None:
        """
        Ensure valid document file (.pdf) is accepted for document asset uploads.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        pdf_file = SimpleUploadedFile(
            name='media_kit.pdf',
            content=b'%PDF-1.4 mock content for pdf media kit',
            content_type='application/pdf'
        )

        response = self.client.post(
            self.upload_url,
            {'file': pdf_file, 'file_type': 'DOCUMENT'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['file_name'], 'media_kit.pdf')

    def test_fake_pdf_rejected_by_magic_bytes(self) -> None:
        """
        Ensure document with .pdf extension but missing '%PDF-' magic bytes is rejected.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        fake_pdf = SimpleUploadedFile(
            name='fake_document.pdf',
            content=b'NOT A REAL PDF FILE HEADER',
            content_type='application/pdf'
        )

        response = self.client.post(
            self.upload_url,
            {'file': fake_pdf, 'file_type': 'DOCUMENT'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid or corrupted PDF document', response.data.get('detail', ''))

    def test_fake_mp4_rejected_by_magic_bytes(self) -> None:
        """
        Ensure video with .mp4 extension but missing 'ftyp' box in first 12 bytes is rejected.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        fake_mp4 = SimpleUploadedFile(
            name='fake_video.mp4',
            content=b'NOT AN MP4 VIDEO AT ALL',
            content_type='video/mp4'
        )

        response = self.client.post(
            self.upload_url,
            {'file': fake_mp4, 'file_type': 'VIDEO'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid or corrupted MP4 video file', response.data.get('detail', ''))

    def test_valid_mp4_video_upload_success(self) -> None:
        """
        Ensure authentic MP4 video file with valid 'ftyp' header is accepted.

        :return: None
        """
        self.client.force_authenticate(user=self.creator_user)
        valid_mp4 = SimpleUploadedFile(
            name='promo.mp4',
            content=b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00video payload',
            content_type='video/mp4'
        )

        response = self.client.post(
            self.upload_url,
            {'file': valid_mp4, 'file_type': 'VIDEO'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['file_name'], 'promo.mp4')


class AdminInfluencerDetailRegressionTests(APITestCase):
    """
    Regression test suite verifying admin influencer detail endpoint
    and nested serializer field configuration (location_text, languages, service areas).
    """

    def setUp(self) -> None:
        """
        Create superuser admin and creator with location and languages.

        :return: None
        """
        from apps.taxonomies.models import Location, LocationType
        from apps.creators.models import CreatorLanguage, CreatorServiceArea

        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin.test@example.com',
            password='AdminPassword123!',
            role=UserRole.SUPER_ADMIN
        )
        self.creator_user = User.objects.create_user(
            username='influencer_sample',
            email='influencer.sample@example.com',
            password='CreatorPassword123!',
            role=UserRole.CREATOR
        )
        self.loc_country = Location.objects.create(
            name='India',
            type=LocationType.COUNTRY,
            country_code='IN'
        )
        self.loc_city = Location.objects.create(
            name='Kochi',
            type=LocationType.CITY,
            parent=self.loc_country,
            country_code='IN',
            latitude='9.9312',
            longitude='76.2673'
        )
        self.creator_profile = CreatorProfile.objects.create(
            user=self.creator_user,
            handle='kochi_creator',
            display_name='Kochi Creator',
            primary_location=self.loc_city
        )
        CreatorLanguage.objects.create(
            creator=self.creator_profile,
            language_code='ml'
        )
        CreatorServiceArea.objects.create(
            creator=self.creator_profile,
            location=self.loc_city
        )
        self.detail_url = reverse('admin_influencers_detail', kwargs={'pk': self.creator_profile.id})

    def test_admin_influencer_detail_success(self) -> None:
        """
        Ensure GET /api/v1/admin/influencers/<id>/ returns HTTP 200 with populated location_text and languages.

        :return: None
        """
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['handle'], 'kochi_creator')
        self.assertEqual(response.data['display_name'], 'Kochi Creator')
        self.assertIn('Kochi', response.data['location_text'])
        self.assertEqual(len(response.data['languages']), 1)
        self.assertEqual(response.data['languages'][0]['language_code'], 'ml')
        self.assertEqual(response.data['languages'][0]['language_name'], 'Malayalam')
        self.assertEqual(len(response.data['service_areas']), 1)
        self.assertEqual(response.data['service_areas'][0]['location']['name'], 'Kochi')


class CreatorMediaKitPdfTests(APITestCase):
    """
    Test suite validating ReportLab branded Media Kit PDF generation,
    storage, and dispatch integration (REQ-INT-02).
    """

    def setUp(self) -> None:
        from apps.creators.models import ProfileStatus, VerificationStatus
        self.creator_user = User.objects.create_user(
            username='mediakit_creator',
            email='mediakit.creator@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR,
            is_active=True
        )
        self.creator = CreatorProfile.objects.create(
            user=self.creator_user,
            handle='mediakit_star',
            display_name='MediaKit Star',
            bio='Lifestyle & Tech creator creating premium reels.',
            status=ProfileStatus.ACTIVE,
            verification_status=VerificationStatus.VERIFIED
        )

    def test_generate_creator_media_kit_pdf_produces_valid_pdf_bytes(self) -> None:
        """
        Ensure generate_creator_media_kit_pdf outputs non-empty bytes starting with %PDF.
        """
        from apps.creators.api.v1.services import generate_creator_media_kit_pdf

        pdf_bytes = generate_creator_media_kit_pdf(self.creator)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 500)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_request_creator_media_kit_service_persists_file_and_returns_url(self) -> None:
        """
        Ensure request_creator_media_kit generates the PDF file on disk
        and returns access download_url.
        """
        import os
        from django.conf import settings
        from apps.creators.api.v1.services import request_creator_media_kit

        payload = {
            'requester_name': 'Acme Marketing',
            'requester_email': 'brand.lead@acme.com',
            'company_name': 'Acme Brands Corp',
            'notes': 'Looking forward to collaboration'
        }

        result = request_creator_media_kit(self.creator.handle, payload)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['creator_handle'], 'mediakit_star')
        self.assertIn('download_url', result)
        self.assertTrue(result['download_url'].endswith(f"{self.creator.id}_mediakit.pdf"))

        expected_file_path = os.path.join(settings.MEDIA_ROOT, 'media_kits', f"{self.creator.id}_mediakit.pdf")
        self.assertTrue(os.path.exists(expected_file_path))

    def test_public_media_kit_endpoint_returns_200(self) -> None:
        """
        POST /api/v1/public/creators/<slug>/media-kit/ must return HTTP 200 with download_url.
        """
        url = f"/api/v1/public/creators/{self.creator.handle}/media-kit/"
        payload = {
            'requester_name': 'Brand Scout',
            'requester_email': 'scout@brands.io',
            'company_name': 'Brand Scout Inc'
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('download_url', response.data)


class CreatorAnalyticsViewTests(APITestCase):
    """
    Test suite validating creator analytics endpoint behavior and tenant boundaries.
    """

    def setUp(self) -> None:
        """Seed creator user, profile, and test inquiries for analytics calculation."""
        from apps.creators.models import PortfolioItem
        self.creator_user = User.objects.create_user(
            username='analytics_creator',
            email='analytics.creator@example.com',
            password='SecurePassword123!',
            role=UserRole.CREATOR
        )
        self.creator_profile = CreatorProfile.objects.create(
            user=self.creator_user,
            handle='analytics_pro',
            display_name='Analytics Pro'
        )
        PortfolioItem.objects.create(
            creator=self.creator_profile,
            title='Featured Campaign Reel',
            views_count=1542,
            media_url='https://example.com/asset.png'
        )
        self.analytics_url = reverse('creator_analytics')

    def test_unauthenticated_analytics_access_denied(self) -> None:
        """Unauthenticated requests must be rejected with 401 Unauthorized."""
        response = self.client.get(self.analytics_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creator_analytics_summary_success(self) -> None:
        """Authenticated creators must receive aggregated analytics summary."""
        self.client.force_authenticate(user=self.creator_user)
        response = self.client.get(self.analytics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['profile_views'], 1542)
        self.assertIn('website_visitors', response.data)
        self.assertIn('total_inquiries', response.data)
        self.assertIn('chart_data', response.data)
        self.assertEqual(len(response.data['chart_data']), 7)

    def test_non_creator_user_analytics_forbidden(self) -> None:
        """Users without a CreatorProfile must receive 403 Forbidden."""
        other_user = User.objects.create_user(
            username='non_creator',
            email='non.creator@example.com',
            password='SecurePassword123!',
            role=UserRole.BUSINESS
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.get(self.analytics_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)



