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

