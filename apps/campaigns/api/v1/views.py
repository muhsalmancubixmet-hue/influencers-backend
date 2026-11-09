from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import ValidationError

from apps.accounts.decorators import require_module_access
from apps.accounts.models import ModuleChoice
from apps.campaigns.models import (
    Campaign,
    CampaignBid,
    Requirement,
    Inquiry,
    InquiryStatus,
    CampaignStatus
)
from apps.campaigns.api.v1.serializers import (
    CampaignListSerializer,
    CampaignDetailSerializer,
    CampaignBidSerializer,
    RequirementSerializer,
    CreatorOpportunityApplySerializer,
    InquirySerializer,
    InquiryMessageSerializer,
    PublicCampaignListSerializer,
    PublicInquiryCreateSerializer
)
from apps.campaigns.api.v1.services import (
    apply_to_campaign,
    send_inquiry_reply,
    moderate_campaign,
    moderate_requirement,
    create_public_inquiry
)
from apps.creators.api.v1.views import get_creator_profile_or_403


class AdminCampaignListView(APIView):
    """Control panel view listing all brand marketplace campaigns."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.CAMPAIGNS, 'VIEW')
    def get(self, request, *args, **kwargs):
        campaigns = Campaign.objects.select_related('business', 'category', 'location').filter(
            is_deleted=False
        ).order_by('-created_at')

        status_param = request.query_params.get('status')
        if status_param:
            campaigns = campaigns.filter(status=status_param.upper())

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(campaigns, request)
        serializer = CampaignListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminCampaignDetailView(APIView):
    """Control panel view inspecting campaign brief, reviewing bids, and toggling status."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.CAMPAIGNS, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            campaign = Campaign.objects.select_related('business', 'category', 'location').prefetch_related(
                'bids__creator'
            ).get(id=pk, is_deleted=False)
        except (Campaign.DoesNotExist, ValueError):
            return Response({'detail': 'Campaign not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CampaignDetailSerializer(campaign)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.CAMPAIGNS, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        is_featured = request.data.get('is_featured')
        status_val = request.data.get('status')

        try:
            campaign = moderate_campaign(
                campaign_id=str(pk),
                is_featured=is_featured if isinstance(is_featured, bool) else None,
                status=status_val,
                admin_user=request.user
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CampaignDetailSerializer(campaign)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminRequirementListView(APIView):
    """Control panel view listing open brand requirements."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.REQUIREMENTS, 'VIEW')
    def get(self, request, *args, **kwargs):
        requirements = Requirement.objects.select_related('business', 'category').filter(
            is_deleted=False
        ).order_by('-created_at')

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(requirements, request)
        serializer = RequirementSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminRequirementDetailView(APIView):
    """Retrieve and moderate an open requirement."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.REQUIREMENTS, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            req = Requirement.objects.select_related('business', 'category', 'location').get(pk=pk, is_deleted=False)
        except Requirement.DoesNotExist:
            return Response({'detail': 'Requirement not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RequirementSerializer(req)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.REQUIREMENTS, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        new_status = request.data.get('status')
        if not new_status:
            return Response({'detail': "Missing 'status' field."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req = moderate_requirement(
                requirement_id=str(pk),
                status=new_status,
                admin_user=request.user
            )
        except ValidationError as err:
            detail = err.message if hasattr(err, 'message') else (err.messages[0] if hasattr(err, 'messages') and err.messages else str(err))
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RequirementSerializer(req)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreatorOpportunitiesListView(APIView):
    """
    Marketplace discovery feed of open campaigns available for creators to apply.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from django.db.models import Q
        campaigns = Campaign.objects.select_related('business', 'category', 'location').filter(
            status__in=[CampaignStatus.PUBLISHED, CampaignStatus.APPLICATIONS],
            is_deleted=False
        ).order_by('-is_featured', '-created_at')

        category = request.query_params.get('category') or request.query_params.get('category_id')
        search = request.query_params.get('search', '').strip()
        location = request.query_params.get('location') or request.query_params.get('location_id')
        platform = request.query_params.get('platform')
        min_budget = request.query_params.get('min_budget')
        max_budget = request.query_params.get('max_budget')

        if category and category.lower() != 'all':
            campaigns = campaigns.filter(
                Q(category_id=category) if (category.isdigit() or len(category) == 36) else (
                    Q(category__name__icontains=category) | Q(category__slug__iexact=category)
                )
            )
        if search:
            campaigns = campaigns.filter(
                Q(title__icontains=search) |
                Q(business__company_name__icontains=search) |
                Q(location_text__icontains=search) |
                Q(deliverables_spec__icontains=search)
            )
        if location:
            campaigns = campaigns.filter(
                Q(location_text__icontains=location) |
                Q(location__name__icontains=location)
            )
        if platform and platform.lower() != 'all':
            campaigns = campaigns.filter(deliverables_spec__icontains=platform)
        if min_budget:
            try:
                campaigns = campaigns.filter(total_budget_cents__gte=int(min_budget) * 100)
            except ValueError:
                pass
        if max_budget:
            try:
                campaigns = campaigns.filter(total_budget_cents__lte=int(max_budget) * 100)
            except ValueError:
                pass

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(campaigns, request)
        serializer = CampaignListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class CreatorOpportunityApplyView(APIView):
    """
    Submit a creator bid and pitch to an open campaign opportunity.
    Strictly scoped to the creator tenant.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required to apply.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CreatorOpportunityApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            bid = apply_to_campaign(
                campaign_id=str(pk),
                creator=profile,
                proposed_fee_cents=serializer.validated_data['proposed_fee_cents'],
                pitch_text=serializer.validated_data['pitch_text']
            )
        except ValidationError as err:
            detail = err.message if hasattr(err, 'message') else (err.messages[0] if hasattr(err, 'messages') and err.messages else str(err))
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = CampaignBidSerializer(bid)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class CreatorInquiryListView(APIView):
    """List direct brand-to-creator inquiries scoped to the authenticated creator."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        inquiries = Inquiry.objects.select_related('business', 'creator').filter(
            creator=profile,
            is_deleted=False
        ).order_by('-updated_at', '-created_at')

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(inquiries, request)
        serializer = InquirySerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class CreatorInquiryMessagesView(APIView):
    """View conversation thread and send reply on a direct inquiry."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            inquiry = Inquiry.objects.get(id=pk, creator=profile, is_deleted=False)
        except (Inquiry.DoesNotExist, ValueError):
            return Response({'detail': 'Inquiry not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Mark incoming unread messages as read when creator opens conversation
        inquiry.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

        messages = inquiry.messages.select_related('sender').filter(is_deleted=False).order_by('created_at')
        serializer = InquiryMessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            inquiry = Inquiry.objects.get(id=pk, creator=profile, is_deleted=False)
        except (Inquiry.DoesNotExist, ValueError):
            return Response({'detail': 'Inquiry not found.'}, status=status.HTTP_404_NOT_FOUND)

        body = request.data.get('body', '').strip()
        offer_price_cents = request.data.get('offer_price_cents')
        if not body:
            return Response({'detail': "Message 'body' cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            msg = send_inquiry_reply(
                inquiry_id=str(inquiry.id),
                sender=request.user,
                body=body,
                offer_price_cents=int(offer_price_cents) if offer_price_cents is not None else None
            )
        except ValidationError as err:
            detail = err.message if hasattr(err, 'message') else (err.messages[0] if hasattr(err, 'messages') and err.messages else str(err))
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

        serializer = InquiryMessageSerializer(msg)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreatorInquiryDetailView(APIView):
    """
    Retrieve single inquiry details or update negotiation status (Accept/Decline).
    Strictly isolated to the authenticated creator's tenant boundary.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        """
        Retrieve detail view for a specific creator collaboration inquiry.

        :param request: Authenticated HTTP request.
        :param pk: UUID of the target inquiry.
        :return: JSON representation of the inquiry.
        """
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            inquiry = Inquiry.objects.select_related('business', 'campaign').get(
                id=pk, creator=profile, is_deleted=False
            )
        except (Inquiry.DoesNotExist, ValueError, ValidationError):
            return Response({'detail': 'Inquiry not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InquirySerializer(inquiry, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk, *args, **kwargs):
        """
        Update the lifecycle status of an inquiry (e.g. ACCEPTED, DECLINED, NEGOTIATING).

        :param request: Authenticated HTTP request containing 'status'.
        :param pk: UUID of the target inquiry.
        :return: Updated JSON representation of the inquiry.
        """
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            inquiry = Inquiry.objects.get(id=pk, creator=profile, is_deleted=False)
        except (Inquiry.DoesNotExist, ValueError, ValidationError):
            return Response({'detail': 'Inquiry not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        if not new_status or new_status not in InquiryStatus.values:
            return Response(
                {'detail': f"Invalid status. Must be one of: {list(InquiryStatus.values)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        inquiry.status = new_status
        inquiry.save(update_fields=['status', 'updated_at'])

        serializer = InquirySerializer(inquiry, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreatorInquiryMarkReadView(APIView):
    """
    Mark all unread incoming messages in an inquiry thread as read for this creator.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        profile = get_creator_profile_or_403(request.user)
        if not profile:
            return Response({'detail': 'Creator profile required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            inquiry = Inquiry.objects.get(id=pk, creator=profile, is_deleted=False)
        except (Inquiry.DoesNotExist, ValueError):
            return Response({'detail': 'Inquiry not found.'}, status=status.HTTP_404_NOT_FOUND)

        marked = inquiry.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        return Response({
            'detail': 'Inquiry marked as read.',
            'marked_count': marked,
            'is_read': True,
            'unread_count': 0
        }, status=status.HTTP_200_OK)


class PublicCampaignListView(APIView):
    """
    Public discovery endpoint listing published campaigns and collaboration opportunities.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        """
        List active marketplace campaigns matching optional category, location, or search.
        
        :param request: Public HTTP request with optional query filters.
        :return: Paginated list of PublicCampaignListSerializer objects.
        """
        campaigns = Campaign.objects.select_related(
            'business', 'category', 'location'
        ).filter(
            status__in=[CampaignStatus.PUBLISHED, CampaignStatus.APPLICATIONS, CampaignStatus.ACTIVE],
            is_deleted=False
        ).order_by('-created_at')

        category = request.query_params.get('category')
        if category:
            campaigns = campaigns.filter(category__name__iexact=category)

        location = request.query_params.get('location')
        if location:
            campaigns = campaigns.filter(location__name__iexact=location)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(campaigns, request)
        serializer = PublicCampaignListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PublicInquiryCreateView(APIView):
    """
    Public collaboration inquiry dispatch endpoint.
    Allows brand clients and visitors to propose campaigns to creators.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Validate inquiry payload and trigger thread creation service.
        
        :param request: Public HTTP request containing collaboration parameters.
        :return: 201 Created with confirmation summary.
        """
        serializer = PublicInquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            inquiry = create_public_inquiry(serializer.validated_data)
            return Response({
                'id': str(inquiry.id),
                'status': inquiry.status,
                'creator': inquiry.creator.handle,
                'business': inquiry.business.company_name,
                'detail': 'Collaboration inquiry submitted successfully. The creator has been notified.'
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            detail = e.message if hasattr(e, 'message') else (e.messages[0] if hasattr(e, 'messages') and e.messages else str(e))
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)

