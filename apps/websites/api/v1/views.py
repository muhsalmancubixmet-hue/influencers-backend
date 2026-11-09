from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.decorators import require_module_access
from apps.accounts.models import ModuleChoice
from apps.websites.models import CreatorWebsite, DomainRecord
from apps.websites.api.v1.serializers import (
    CreatorWebsiteSerializer,
    DomainRecordSerializer,
    ConnectCustomDomainSerializer,
    AdminWebsiteSerializer
)
from apps.websites.api.v1.services import (
    get_or_create_creator_website,
    update_website_settings,
    connect_website_domain,
    verify_custom_domain_dns
)
from apps.creators.api.v1.views import get_creator_profile_or_403


class CreatorWebsiteView(APIView):
    """Creator website wizard configuration endpoint."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        website = get_or_create_creator_website(profile)
        serializer = CreatorWebsiteSerializer(website)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        website = get_or_create_creator_website(profile)
        updated = update_website_settings(website, request.data)
        serializer = CreatorWebsiteSerializer(updated)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreatorWebsiteDomainView(APIView):
    """Connect a custom domain and retrieve DNS instructions."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        website = get_or_create_creator_website(profile)
        records = website.domain_records.filter(is_deleted=False).order_by('-created_at')
        serializer = DomainRecordSerializer(records, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        website = get_or_create_creator_website(profile)
        serializer = ConnectCustomDomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            record = connect_website_domain(
                website=website,
                domain=serializer.validated_data['domain']
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = DomainRecordSerializer(record)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class AdminDomainListView(APIView):
    """Control panel view listing all custom domain mappings."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.DOMAINS, 'VIEW')
    def get(self, request, *args, **kwargs):
        domains = DomainRecord.objects.select_related('website__creator').filter(
            is_deleted=False
        ).order_by('-created_at')

        status_param = request.query_params.get('status')
        if status_param:
            domains = domains.filter(verification_status=status_param.upper())

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(domains, request)
        serializer = DomainRecordSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminDomainVerifyView(APIView):
    """Trigger automated or simulated DNS & TLS verification probe."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.DOMAINS, 'MANAGE')
    def post(self, request, pk, *args, **kwargs):
        simulated = request.data.get('simulated', True)
        try:
            result = verify_custom_domain_dns(
                domain_record_id=str(pk),
                simulated=bool(simulated)
            )
        except Exception as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class AdminWebsiteListView(APIView):
    """
    Control panel view listing all deployed creator websites.
    Enables search by creator handle/title and filtering by status.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.WEBSITES, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        List creator websites with search and status filtering.

        :param request: Authenticated administrative HTTP request.
        :return: Paginated JSON list of creator websites.
        """
        websites = CreatorWebsite.objects.select_related('creator').prefetch_related(
            'domain_records'
        ).filter(is_deleted=False).order_by('-created_at')

        # Filter by status
        status_param = request.query_params.get('status')
        if status_param and status_param.lower() != 'all':
            websites = websites.filter(status=status_param.upper())

        # Search by title, subdomain, creator name, or handle
        q = request.query_params.get('q', '').strip()
        if q:
            websites = websites.filter(
                models.Q(title__icontains=q) |
                models.Q(subdomain__icontains=q) |
                models.Q(creator__display_name__icontains=q) |
                models.Q(creator__handle__icontains=q)
            )

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(websites, request)
        serializer = AdminWebsiteSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminWebsiteDetailView(APIView):
    """
    Administrative control endpoint for moderating or suspending a creator website.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.WEBSITES, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        """Retrieve full website detail."""
        try:
            site = CreatorWebsite.objects.select_related('creator').get(id=pk, is_deleted=False)
        except (CreatorWebsite.DoesNotExist, ValueError):
            return Response({'detail': 'Website not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminWebsiteSerializer(site)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.WEBSITES, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        """Moderate website status (e.g. SUSPENDED, PUBLISHED)."""
        try:
            site = CreatorWebsite.objects.get(id=pk, is_deleted=False)
        except (CreatorWebsite.DoesNotExist, ValueError):
            return Response({'detail': 'Website not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if new_status:
            site.status = new_status.upper()
            if site.status == 'PUBLISHED':
                site.is_published = True
            elif site.status == 'SUSPENDED':
                site.is_published = False
            site.save(update_fields=['status', 'is_published'])

        serializer = AdminWebsiteSerializer(site)
        return Response(serializer.data, status=status.HTTP_200_OK)
