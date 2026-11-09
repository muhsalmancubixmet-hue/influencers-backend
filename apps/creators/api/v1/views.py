from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.accounts.decorators import require_module_access
from apps.accounts.models import ModuleChoice
from apps.creators.models import (
    CreatorProfile,
    PortfolioItem,
    CreatorService,
    SocialAccount
)
from apps.common.models import SocialPlatform, PlatformRequest
from apps.creators.api.v1.serializers import (
    CreatorProfileSerializer,
    PortfolioItemSerializer,
    CreatorServiceSerializer,
    AdminInfluencerListSerializer,
    AdminInfluencerDetailSerializer,
    AdminInfluencerModerationSerializer,
    AdminInfluencerCreateSerializer,
    SocialAccountSerializer,
    SocialAccountConnectSerializer,
    PublicCreatorListSerializer,
    PublicCreatorDetailSerializer
)
from apps.common.api.v1.serializers import (
    SocialPlatformSerializer,
    PlatformRequestSerializer
)
from apps.creators.api.v1.services import (
    update_creator_profile,
    reorder_portfolio,
    moderate_creator,
    connect_social_account,
    disconnect_social_account,
    get_public_creators,
    get_public_creator_detail
)
from apps.common.api.v1.services import (
    record_audit_log,
    create_creator_platform_request
)


def get_creator_profile_or_403(user):
    """Ensure user has an active creator profile tenant boundary."""
    profile = getattr(user, 'creator_profile', None)
    if not profile or profile.is_deleted:
        return None
    return profile


class CreatorProfileView(APIView):
    """
    Creator Workspace profile configuration endpoint.
    Strictly scoped to the authenticated user's CreatorProfile.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found for this account.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreatorProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found for this account.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreatorProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_profile = update_creator_profile(profile, serializer.validated_data)
        out_serializer = CreatorProfileSerializer(updated_profile)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class CreatorPortfolioListCreateView(APIView):
    """List or create portfolio showcase items for the authenticated creator."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        items = profile.portfolio_items.filter(is_deleted=False).order_by('order', '-created_at')
        serializer = PortfolioItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PortfolioItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(creator=profile)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreatorPortfolioDetailView(APIView):
    """Update or remove a portfolio item owned by the authenticated creator."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            item = profile.portfolio_items.get(id=pk, is_deleted=False)
        except (PortfolioItem.DoesNotExist, ValueError):
            return Response({'detail': 'Portfolio item not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PortfolioItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            item = profile.portfolio_items.get(id=pk, is_deleted=False)
        except (PortfolioItem.DoesNotExist, ValueError):
            return Response({'detail': 'Portfolio item not found.'}, status=status.HTTP_404_NOT_FOUND)

        item.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreatorPortfolioReorderView(APIView):
    """Reorder portfolio items for the authenticated creator."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        orders = request.data.get('orders', [])
        reorder_portfolio(profile, orders)
        return Response({'detail': 'Portfolio reordered successfully.'}, status=status.HTTP_200_OK)


class CreatorServiceListCreateView(APIView):
    """List or create custom service offerings for the authenticated creator."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        services = profile.services.filter(is_deleted=False).order_by('-created_at')
        serializer = CreatorServiceSerializer(services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreatorServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(creator=profile)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreatorServiceDetailView(APIView):
    """Update or delete a creator service package."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            srv = profile.services.get(id=pk, is_deleted=False)
        except (CreatorService.DoesNotExist, ValueError):
            return Response({'detail': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CreatorServiceSerializer(srv, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            srv = profile.services.get(id=pk, is_deleted=False)
        except (CreatorService.DoesNotExist, ValueError):
            return Response({'detail': 'Service not found.'}, status=status.HTTP_404_NOT_FOUND)

        srv.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminInfluencerListView(APIView):
    """Control panel view listing all influencers."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.INFLUENCERS, 'VIEW')
    def get(self, request, *args, **kwargs):
        creators = CreatorProfile.objects.select_related('user', 'primary_location').prefetch_related(
            'categories__category'
        ).filter(is_deleted=False).order_by('-created_at')

        search = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status')
        verification_filter = request.query_params.get('verification_status')

        if search:
            creators = creators.filter(
                display_name__icontains=search
            ) | creators.filter(
                handle__icontains=search
            ) | creators.filter(
                user__email__icontains=search
            )
        if status_filter:
            creators = creators.filter(status=status_filter.upper())
        if verification_filter:
            creators = creators.filter(verification_status=verification_filter.upper())

        category_filter = request.query_params.get('category')
        if category_filter:
            creators = creators.filter(categories__category__name__iexact=category_filter)

        country_filter = request.query_params.get('country')
        if country_filter:
            creators = creators.filter(primary_location__country_code__iexact=country_filter)

        city_filter = request.query_params.get('city')
        if city_filter:
            creators = creators.filter(primary_location__name__iexact=city_filter)

        platform_filter = request.query_params.get('platform')
        if platform_filter:
            creators = creators.filter(social_accounts__platform__name__iexact=platform_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(creators, request)
        serializer = AdminInfluencerListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @require_module_access(ModuleChoice.INFLUENCERS, 'MANAGE')
    def post(self, request, *args, **kwargs):
        """Admin endpoint to manually onboard/invite a creator."""
        serializer = AdminInfluencerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # -------------------------------------------------------------
        # STEP 1: Persist user account and creator profile atomically
        # -------------------------------------------------------------
        with transaction.atomic():
            from apps.accounts.models import User, UserRole
            from apps.taxonomies.models import Category
            from apps.creators.models import CreatorCategory, VerificationStatus, ProfileStatus
            import secrets
            from django.core.signing import TimestampSigner
            from apps.accounts.tasks import send_verification_email_task

            email = data['email']
            handle = data['handle']
            name = data['name'].strip()
            first_name = name.split()[0] if name else ""
            last_name = " ".join(name.split()[1:]) if len(name.split()) > 1 else ""

            # Generate strong temporary onboarding password
            temp_password = secrets.token_urlsafe(10)

            user = User.objects.create(
                email=email,
                username=handle,
                first_name=first_name,
                last_name=last_name,
                role=UserRole.CREATOR,
                is_active=True
            )
            user.set_password(temp_password)
            user.save()

            creator = CreatorProfile.objects.create(
                user=user,
                handle=handle,
                display_name=name,
                verification_status=VerificationStatus.UNVERIFIED,
                status=ProfileStatus.ACTIVE
            )

            category_name = data.get('category', '').strip()
            if category_name:
                category_obj = Category.objects.filter(name__iexact=category_name).first()
                if not category_obj:
                    category_obj = Category.objects.create(
                        name=category_name,
                        slug=category_name.lower().replace(' ', '-')
                    )
                CreatorCategory.objects.create(
                    creator=creator,
                    category=category_obj
                )

            # Generate cryptographically signed verification token
            signer = TimestampSigner()
            verification_token = signer.sign(str(user.id))

        # -------------------------------------------------------------
        # STEP 2: Dispatch asynchronous welcome email task via Celery
        # -------------------------------------------------------------
        try:
            send_verification_email_task.delay(
                str(user.id),
                user.email,
                verification_token,
                temp_password
            )
        except Exception:
            # Fallback direct dispatch if message broker queue is disconnected
            try:
                send_verification_email_task(
                    None,
                    str(user.id),
                    user.email,
                    verification_token,
                    temp_password
                )
            except Exception:
                pass

        # -------------------------------------------------------------
        # STEP 3: Record audit log for security compliance
        # -------------------------------------------------------------
        record_audit_log(
            admin=request.user,
            action='ONBOARD_INFLUENCER',
            entity='CreatorProfile',
            entity_id=str(creator.id),
            request=request,
            reason=f"Manually onboarded influencer {creator.handle} ({creator.display_name})"
        )

        out_serializer = AdminInfluencerListSerializer(creator)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)



class AdminInfluencerDetailView(APIView):
    """Control panel view to inspect and moderate an influencer."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.INFLUENCERS, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            creator = CreatorProfile.objects.select_related(
                'user', 'primary_location', 'current_location'
            ).prefetch_related(
                'categories__category',
                'languages',
                'service_areas__location',
                'social_accounts__platform',
                'portfolio_items',
                'services__service_type'
            ).get(id=pk, is_deleted=False)
        except (CreatorProfile.DoesNotExist, ValueError):
            return Response({'detail': 'Creator not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminInfluencerDetailSerializer(creator)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.INFLUENCERS, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        serializer = AdminInfluencerModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            creator = moderate_creator(
                creator_id=str(pk),
                status=serializer.validated_data.get('status'),
                verification_status=serializer.validated_data.get('verification_status'),
                admin_user=request.user
            )
        except ValidationError as err:
            detail = err.message if hasattr(err, 'message') else (err.messages[0] if hasattr(err, 'messages') and err.messages else str(err))
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = AdminInfluencerDetailSerializer(creator)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class CreatorMediaUploadView(APIView):
    """
    Multipart upload endpoint for creator avatar, cover banner, and portfolio assets.
    """
    permission_classes = [IsAuthenticated]

    # Security constraints for file uploads per BACKEND_ENGINEERING_RULES Section 5
    MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB maximum upload limit
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf', '.mp4'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    BLOCKED_EXTENSIONS = {'.svg', '.html', '.htm', '.xhtml', '.js', '.exe', '.sh', '.bat', '.php'}

    def post(self, request, *args, **kwargs):
        """
        Receive uploaded file, validate size, extension, and image integrity, persist to disk/storage,
        record MediaAsset, and update profile if applicable.

        :param request: Authenticated HTTP request containing multipart 'file' and optional 'file_type'.
        :return: JSON response with file URL and MediaAsset metadata, or 400 Bad Request if validation fails.
        :raises None: Validation failures return formatted Response objects.
        """
        import os
        import uuid
        from django.conf import settings
        from django.core.files.storage import default_storage
        from PIL import Image
        from apps.common.models import MediaAsset, MediaType

        # Step 1: Validate creator profile ownership and access boundary
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Step 2: Ensure file was provided in multipart payload
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'detail': "No file provided in 'file' field."}, status=status.HTTP_400_BAD_REQUEST)

        # Step 3: Validate file size (10 MB maximum limit)
        if uploaded_file.size > self.MAX_UPLOAD_SIZE_BYTES:
            return Response(
                {'detail': 'File size exceeds maximum allowed limit of 10MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 4: Validate extension against whitelist and blocked list (.svg, .html, etc.)
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext in self.BLOCKED_EXTENSIONS or ext not in self.ALLOWED_EXTENSIONS:
            return Response(
                {'detail': f'File type "{ext}" is not permitted.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 5: For image formats, verify file integrity and structure with Pillow
        if ext in self.IMAGE_EXTENSIONS:
            try:
                img = Image.open(uploaded_file)
                img.verify()
                # Reset file read pointer after Pillow verification
                uploaded_file.seek(0)
            except Exception:
                return Response(
                    {'detail': 'Invalid or corrupted image content.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Step 6: Magic byte validation for PDF documents (must start with %PDF-)
        if ext == '.pdf':
            header = uploaded_file.read(5)
            uploaded_file.seek(0)
            if not header.startswith(b'%PDF-'):
                return Response(
                    {'detail': 'Invalid or corrupted PDF document.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Step 7: Magic byte validation for MP4 videos (must contain 'ftyp' in first 12 bytes)
        if ext == '.mp4':
            header = uploaded_file.read(12)
            uploaded_file.seek(0)
            if b'ftyp' not in header:
                return Response(
                    {'detail': 'Invalid or corrupted MP4 video file.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        file_type_param = request.data.get('file_type', 'IMAGE').upper()
        # Map param to MediaType choice
        type_mapping = {
            'AVATAR': MediaType.AVATAR,
            'COVER': MediaType.COVER,
            'IMAGE': MediaType.IMAGE,
            'VIDEO': MediaType.VIDEO,
            'DOCUMENT': MediaType.DOCUMENT,
        }
        asset_type = type_mapping.get(file_type_param, MediaType.IMAGE)

        # Generate unique storage filename with server-controlled UUID
        unique_name = f"creators/{profile.id}/{uuid.uuid4().hex}{ext}"
        saved_path = default_storage.save(unique_name, uploaded_file)
        relative_url = default_storage.url(saved_path)

        # Build absolute URL if needed or use relative URL
        full_url = request.build_absolute_uri(relative_url)

        # Record MediaAsset entity
        media_asset = MediaAsset.objects.create(
            uploader=request.user,
            file_name=uploaded_file.name,
            file_type=asset_type,
            file_size_bytes=uploaded_file.size,
            cdn_url=full_url,
            mime_type=uploaded_file.content_type or 'application/octet-stream'
        )

        # Automatically update profile photo_url or cover_url if appropriate
        if asset_type == MediaType.AVATAR or file_type_param == 'AVATAR':
            profile.photo_url = full_url
            profile.save(update_fields=['photo_url'])
        elif asset_type == MediaType.COVER or file_type_param == 'COVER':
            profile.cover_url = full_url
            profile.save(update_fields=['cover_url'])

        return Response({
            'id': str(media_asset.id),
            'url': full_url,
            'file_name': media_asset.file_name,
            'file_type': media_asset.file_type,
            'file_size_bytes': media_asset.file_size_bytes
        }, status=status.HTTP_201_CREATED)


class CreatorSocialPlatformListView(APIView):
    """
    Catalog of all active supported social networks.
    
    Allows Creator Hub UI to populate dynamic connection dropdowns.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        List active social platforms.
        
        :param request: Authenticated HTTP request.
        :return: JSON array of supported social platforms.
        """
        platforms = SocialPlatform.objects.filter(is_active=True, is_deleted=False).order_by('name')
        serializer = SocialPlatformSerializer(platforms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreatorSocialAccountListCreateView(APIView):
    """
    Creator Workspace social media channels list and connect endpoint.
    
    Strictly isolated to the authenticated creator's profile.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        List all connected social channels for the authenticated creator.
        
        :param request: Authenticated HTTP request.
        :return: JSON array of connected social channels.
        """
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        accounts = SocialAccount.objects.filter(
            creator=profile,
            is_deleted=False
        ).select_related('platform').order_by('-created_at')

        serializer = SocialAccountSerializer(accounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """
        Connect or update an external social media channel.
        
        :param request: Authenticated HTTP request containing channel payload.
        :return: 201 Created with persisted social account data, or 400 Bad Request with readable detail message.
        """
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SocialAccountConnectSerializer(data=request.data)
        if not serializer.is_valid():
            # Format the first field-level validation error into a readable detail message
            detail_msg = "Invalid data submitted."
            for field, err_list in serializer.errors.items():
                if isinstance(err_list, list) and err_list:
                    detail_msg = f"{field}: {err_list[0]}"
                    break
                elif isinstance(err_list, str):
                    detail_msg = f"{field}: {err_list}"
                    break
            return Response({'detail': str(detail_msg), 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = connect_social_account(
                profile=profile,
                platform_identifier=serializer.validated_data['platform'],
                username=serializer.validated_data['username'],
                profile_url=serializer.validated_data['profile_url'],
                followers_count=serializer.validated_data.get('followers_count', 0),
                following_count=serializer.validated_data.get('following_count', 0),
                engagement_rate=serializer.validated_data.get('engagement_rate', 0.0)
            )
            return Response(SocialAccountSerializer(account).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            detail = e.message if hasattr(e, 'message') else (e.messages[0] if hasattr(e, 'messages') and e.messages else str(e))
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)


class CreatorSocialAccountDetailView(APIView):
    """
    Channel management and disconnection endpoint.
    
    Strictly enforces creator tenant boundary isolation.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, *args, **kwargs):
        """
        Disconnect a social media channel.
        
        :param request: Authenticated HTTP request.
        :param pk: UUID of the SocialAccount.
        :return: 200 OK confirmation.
        """
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            disconnect_social_account(profile, str(pk))
            return Response({'detail': 'Social channel disconnected successfully.'}, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)


class CreatorPlatformRequestCreateView(APIView):
    """
    Endpoint for creators to petition for unlisted social networks.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Submit a new platform request petition.
        
        :param request: Authenticated HTTP request with platform name and URL.
        :return: 201 Created with submitted petition.
        """
        platform_name = request.data.get('platform_name') or request.data.get('name')
        profile_url = request.data.get('profile_url') or request.data.get('url', '')
        note = request.data.get('note') or request.data.get('reason', '')

        if not platform_name or not str(platform_name).strip():
            return Response({'detail': 'platform_name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req = create_creator_platform_request(
                user=request.user,
                platform_name=str(platform_name).strip(),
                profile_url=str(profile_url).strip(),
                note=str(note).strip()
            )
            return Response(PlatformRequestSerializer(req).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PublicCreatorListView(APIView):
    """
    Public directory endpoint listing active creators for marketplace discovery.
    Allows unauthenticated clients and search crawlers to query creator cards.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """
        List active creators with full filtering and pagination.
        
        :param request: Public HTTP request with optional query filters.
        :return: Paginated list of PublicCreatorListSerializer objects.
        """
        creators = get_public_creators(request.query_params)
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(creators, request)
        serializer = PublicCreatorListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PublicCreatorDetailView(APIView):
    """
    Public profile endpoint displaying portfolio, services, and rates for an influencer.
    """
    permission_classes = [AllowAny]

    def get(self, request, slug, *args, **kwargs):
        """
        Retrieve creator detail by handle or slug.
        
        :param request: Public HTTP request.
        :param slug: Unique handle or slug identifier.
        :return: JSON object of creator showcase or 404.
        """
        creator = get_public_creator_detail(slug)
        if not creator:
            return Response(
                {'detail': f"Creator '{slug}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = PublicCreatorDetailSerializer(creator)
        return Response(serializer.data, status=status.HTTP_200_OK)


