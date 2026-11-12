from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.core.exceptions import ValidationError

from apps.accounts.decorators import require_module_access
from apps.accounts.models import ModuleChoice
from apps.common.models import (
    SocialPlatform,
    PlatformRequest,
    PlatformSetting,
    SupportTicket,
    TicketMessage,
    AuditLog,
    Notification,
    ServiceType,
    MediaAsset
)
from apps.common.api.v1.serializers import (
    SocialPlatformSerializer,
    PlatformRequestSerializer,
    PlatformRequestReviewSerializer,
    PlatformSettingSerializer,
    SupportTicketSerializer,
    StaffTicketMessageSerializer,
    AuditLogSerializer,
    NotificationSerializer,
    ServiceTypeSerializer,
    MediaAssetSerializer
)
from apps.common.api.v1.services import (
    review_platform_request,
    update_platform_setting,
    add_ticket_message,
    dispatch_broadcast_notification,
    record_audit_log
)


class AdminSocialPlatformListCreateView(APIView):
    """List and register supported social networks."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SOCIAL_PLATFORMS, 'VIEW')
    def get(self, request, *args, **kwargs):
        platforms = SocialPlatform.objects.filter(is_deleted=False).order_by('name')
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(platforms, request)
        serializer = SocialPlatformSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @require_module_access(ModuleChoice.SOCIAL_PLATFORMS, 'MANAGE')
    def post(self, request, *args, **kwargs):
        serializer = SocialPlatformSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        platform = serializer.save()
        record_audit_log(
            admin=request.user,
            action='CREATE_SOCIAL_PLATFORM',
            entity='SocialPlatform',
            entity_id=str(platform.id),
            request=request,
            reason=f"Registered social platform {platform.name}"
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminSocialPlatformDetailView(APIView):
    """Retrieve or update social network settings."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SOCIAL_PLATFORMS, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        try:
            platform = SocialPlatform.objects.get(id=pk, is_deleted=False)
        except (SocialPlatform.DoesNotExist, ValueError):
            return Response({'detail': 'SocialPlatform not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SocialPlatformSerializer(platform, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        platform = serializer.save()
        record_audit_log(
            admin=request.user,
            action='UPDATE_SOCIAL_PLATFORM',
            entity='SocialPlatform',
            entity_id=str(platform.id),
            request=request,
            reason=f"Updated social platform config for {platform.name}"
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminPlatformRequestListView(APIView):
    """List user-submitted petitions for new platform integrations."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SOCIAL_PLATFORMS, 'VIEW')
    def get(self, request, *args, **kwargs):
        requests_qs = PlatformRequest.objects.select_related('requested_by', 'reviewed_by').filter(
            is_deleted=False
        ).order_by('-created_at')

        status_filter = request.query_params.get('status')
        if status_filter:
            requests_qs = requests_qs.filter(status=status_filter.upper())

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(requests_qs, request)
        serializer = PlatformRequestSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminPlatformRequestReviewView(APIView):
    """Approve or reject a platform integration petition."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SOCIAL_PLATFORMS, 'MANAGE')
    def post(self, request, pk, *args, **kwargs):
        serializer = PlatformRequestReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            req = review_platform_request(
                request_id=str(pk),
                new_status=serializer.validated_data['status'],
                reviewer=request.user
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = PlatformRequestSerializer(req)
        return Response(out_serializer.data, status=status.HTTP_200_OK)


class AdminPlatformSettingListView(APIView):
    """List all system dynamic settings."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        settings_qs = PlatformSetting.objects.filter(is_deleted=False).order_by('section', 'key')
        section = request.query_params.get('section')
        if section:
            settings_qs = settings_qs.filter(section=section)

        serializer = PlatformSettingSerializer(settings_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminPlatformSettingDetailView(APIView):
    """Retrieve or update dynamic configuration parameters."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, key, *args, **kwargs):
        try:
            setting = PlatformSetting.objects.get(key=key, is_deleted=False)
        except PlatformSetting.DoesNotExist:
            return Response({'detail': f"Setting '{key}' not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlatformSettingSerializer(setting)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SETTINGS, 'MANAGE')
    def patch(self, request, key, *args, **kwargs):
        if 'value_json' not in request.data:
            return Response({'detail': "Missing 'value_json' payload."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            setting = update_platform_setting(
                key=key,
                value_json=request.data['value_json'],
                updater=request.user
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PlatformSettingSerializer(setting)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminSupportTicketListView(APIView):
    """List support helpdesk tickets with triage filters."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SUPPORT, 'VIEW')
    def get(self, request, *args, **kwargs):
        tickets = SupportTicket.objects.select_related('user', 'assignee').filter(
            is_deleted=False
        ).order_by('-created_at')

        status_param = request.query_params.get('status')
        priority_param = request.query_params.get('priority')
        category_param = request.query_params.get('category')

        if status_param:
            tickets = tickets.filter(status=status_param.upper())
        if priority_param:
            tickets = tickets.filter(priority=priority_param.upper())
        if category_param:
            tickets = tickets.filter(category__iexact=category_param)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(tickets, request)
        serializer = SupportTicketSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminSupportTicketDetailView(APIView):
    """Retrieve ticket details or update status/priority/assignee."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SUPPORT, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            ticket = SupportTicket.objects.select_related('user', 'assignee').get(
                id=pk,
                is_deleted=False
            )
        except (SupportTicket.DoesNotExist, ValueError):
            return Response({'detail': 'SupportTicket not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupportTicketSerializer(ticket)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SUPPORT, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        try:
            ticket = SupportTicket.objects.get(id=pk, is_deleted=False)
        except (SupportTicket.DoesNotExist, ValueError):
            return Response({'detail': 'SupportTicket not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupportTicketSerializer(ticket, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminSupportTicketMessagesView(APIView):
    """
    Read ticket message thread (including staff internal notes) and post replies.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SUPPORT, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            ticket = SupportTicket.objects.get(id=pk, is_deleted=False)
        except (SupportTicket.DoesNotExist, ValueError):
            return Response({'detail': 'SupportTicket not found.'}, status=status.HTTP_404_NOT_FOUND)

        messages = ticket.messages.select_related('author').filter(is_deleted=False).order_by('created_at')
        serializer = StaffTicketMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SUPPORT, 'MANAGE')
    def post(self, request, pk, *args, **kwargs):
        body = request.data.get('body', '').strip()
        if not body:
            return Response({'detail': "Message 'body' cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)

        is_internal_note = bool(request.data.get('is_internal_note', False))
        attachment_url = request.data.get('attachment_url', '')

        try:
            msg = add_ticket_message(
                ticket_id=str(pk),
                author=request.user,
                body=body,
                is_staff=True,
                is_internal_note=is_internal_note,
                attachment_url=attachment_url
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = StaffTicketMessageSerializer(msg)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminAuditLogListView(APIView):
    """Query immutable audit log entries."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.AUDIT_LOGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        logs = AuditLog.objects.select_related('admin').filter(is_deleted=False).order_by('-created_at')

        entity_param = request.query_params.get('entity')
        action_param = request.query_params.get('action')
        if entity_param:
            logs = logs.filter(entity__iexact=entity_param)
        if action_param:
            logs = logs.filter(action__iexact=action_param)

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(logs, request)
        serializer = AuditLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminNotificationListCreateView(APIView):
    """List notifications or dispatch broadcast announcements."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        notifications = Notification.objects.select_related('recipient').filter(
            is_deleted=False
        ).order_by('-created_at')

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(notifications, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @require_module_access(ModuleChoice.SETTINGS, 'MANAGE')
    def post(self, request, *args, **kwargs):
        """
        Dispatch a platform broadcast announcement or direct user notification.

        :param request: Authenticated HTTP request with title, message, audience, and optional recipient.
        :return: Created Notification details.
        """
        from apps.accounts.models import User
        from apps.common.models import NotificationStatus

        title = request.data.get('title', '').strip()
        message = request.data.get('message', '').strip()
        audience = request.data.get('audience', 'All users').strip()
        kind = request.data.get('kind', 'SYSTEM')
        recipient_email = request.data.get('recipient_email', '').strip()
        recipient_id = request.data.get('recipient_id')

        if not title or not message:
            return Response({'detail': "Both 'title' and 'message' are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize kind to uppercase
        clean_kind = str(kind).upper().strip()

        recipient_user = None
        if recipient_id:
            recipient_user = User.objects.filter(id=recipient_id).first()
        elif recipient_email:
            recipient_user = User.objects.filter(email__iexact=recipient_email).first()

        if recipient_user:
            notification = Notification.objects.create(
                recipient=recipient_user,
                title=title,
                message=message,
                kind=clean_kind,
                audience=audience or 'Direct',
                status=NotificationStatus.SENT
            )
            reason_text = f"Dispatched direct {clean_kind} notification '{title}' to {recipient_user.email}"
        else:
            notification = dispatch_broadcast_notification(
                title=title,
                message=message,
                audience=audience,
                kind=clean_kind
            )
            reason_text = f"Dispatched {clean_kind} broadcast '{title}' to {audience}"

        record_audit_log(
            admin=request.user,
            action='DISPATCH_NOTIFICATION',
            entity='Notification',
            entity_id=str(notification.id),
            request=request,
            reason=reason_text
        )

        serializer = NotificationSerializer(notification)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreatorNotificationListView(APIView):
    """
    Creator workspace endpoint retrieving broadcast announcements and direct creator alerts.
    Enforces tenant boundaries: returns only notifications destined for this creator.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        List notifications relevant to the authenticated creator.

        :param request: Authenticated HTTP request with creator JWT.
        :return: JSON array of relevant notifications.
        """
        from django.db.models import Q
        from apps.common.models import NotificationStatus

        user = request.user
        notifications = Notification.objects.filter(
            Q(recipient=user) | Q(
                recipient__isnull=True,
                audience__in=['All users', 'All influencers', 'Pro influencers', 'Premium influencers', '']
            ),
            status=NotificationStatus.SENT,
            is_deleted=False
        ).order_by('-created_at')[:40]

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BusinessNotificationListView(APIView):
    """
    Business portal endpoint retrieving broadcast announcements and direct brand notices.
    Enforces tenant boundaries: returns only notifications destined for this business.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        List notifications relevant to the authenticated business user.

        :param request: Authenticated HTTP request with business JWT.
        :return: JSON array of relevant notifications.
        """
        from django.db.models import Q
        from apps.common.models import NotificationStatus

        user = request.user
        notifications = Notification.objects.filter(
            Q(recipient=user) | Q(
                recipient__isnull=True,
                audience__in=['All users', 'All businesses', 'Business Pro', 'Agency accounts', '']
            ),
            status=NotificationStatus.SENT,
            is_deleted=False
        ).order_by('-created_at')[:40]

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    """
    Mark a notification as read for the authenticated recipient.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, *args, **kwargs):
        """
        Set is_read flag to true on the targeted notification.

        :param request: Authenticated HTTP request.
        :param pk: UUID of targeted Notification.
        :return: Confirmation status dictionary.
        """
        try:
            notif = Notification.objects.get(id=pk, is_deleted=False)
        except (Notification.DoesNotExist, ValueError):
            return Response({'detail': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)

        notif.is_read = True
        notif.save(update_fields=['is_read', 'updated_at'])
        return Response({'status': 'read'}, status=status.HTTP_200_OK)

    def post(self, request, pk, *args, **kwargs):
        """Allow POST alias for clients marking notifications read."""
        return self.patch(request, pk, *args, **kwargs)


class AdminVerificationQueueView(APIView):
    """
    Consolidated administrative moderation queue for creators, social platforms, and businesses.
    Adheres strictly to BACKEND_ENGINEERING_RULES.md RBAC standards.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.INFLUENCERS, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        Aggregate pending verification items across Creators, Social Petitions, and Businesses.

        :param request: Authenticated administrative HTTP request.
        :return: JSON array of verification queue items.
        """
        from apps.creators.models import CreatorProfile, VerificationStatus
        from apps.businesses.models import BusinessProfile, BusinessVerificationStatus
        from apps.common.models import PlatformRequest, PlatformRequestStatus

        items = []

        # 1. Creators awaiting verification
        creators = CreatorProfile.objects.select_related('user').filter(
            verification_status__in=[VerificationStatus.UNVERIFIED, 'PENDING'],
            is_deleted=False
        ).order_by('-created_at')[:25]

        for c in creators:
            items.append({
                'id': str(c.id),
                'user': c.display_name or c.handle,
                'email': c.user.email if c.user else "",
                'detail': f"Handle: @{c.handle} · Category: {c.primary_city or 'Global'}",
                'kind': 'creator',
                'status': 'pending' if c.verification_status in [VerificationStatus.UNVERIFIED, 'PENDING'] else str(c.verification_status).lower(),
                'submitted': c.created_at.strftime("%b %d, %Y") if c.created_at else "Recent",
                'entity_id': str(c.id),
            })

        # 2. Social Petitions / Platforms
        petitions = PlatformRequest.objects.select_related('requested_by').filter(
            is_deleted=False
        ).order_by('-created_at')[:25]

        for p in petitions:
            user_label = p.requested_by.email if p.requested_by else "Creator"
            items.append({
                'id': str(p.id),
                'user': p.platform_name,
                'email': user_label,
                'detail': f"Requested by {user_label} · {p.profile_url or p.note or 'Custom network'}",
                'kind': 'social',
                'status': 'pending' if p.status == PlatformRequestStatus.PENDING else str(p.status).lower(),
                'submitted': p.created_at.strftime("%b %d, %Y") if p.created_at else "Recent",
                'entity_id': str(p.id),
            })

        # 3. Businesses awaiting verification
        businesses = BusinessProfile.objects.select_related('user').filter(
            is_deleted=False
        ).order_by('-created_at')[:25]

        for b in businesses:
            b_status = getattr(b, 'verification_status', BusinessVerificationStatus.PENDING)
            items.append({
                'id': str(b.id),
                'user': b.company_name,
                'email': b.user.email if b.user else "",
                'detail': f"Vertical: {b.business_type or 'General'} · Contact: {b.contact_name or b.contact_email}",
                'kind': 'business',
                'status': 'pending' if b_status in [BusinessVerificationStatus.UNVERIFIED, BusinessVerificationStatus.PENDING] else str(b_status).lower(),
                'submitted': b.created_at.strftime("%b %d, %Y") if b.created_at else "Recent",
                'entity_id': str(b.id),
            })

        return Response(items, status=status.HTTP_200_OK)


class AdminServiceTypeListCreateView(APIView):
    """List and create creator deliverable service catalog archetypes."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        services = ServiceType.objects.select_related('platform').filter(is_deleted=False).order_by('name')
        search = request.query_params.get('search', '').strip()
        if search:
            services = services.filter(name__icontains=search)
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(services, request)
        serializer = ServiceTypeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @require_module_access(ModuleChoice.SETTINGS, 'MANAGE')
    def post(self, request, *args, **kwargs):
        serializer = ServiceTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = serializer.save()
        record_audit_log(
            admin=request.user,
            action='CREATE_SERVICE_TYPE',
            entity='ServiceType',
            entity_id=str(service.id),
            request=request,
            reason=f"Created deliverable service {service.name}"
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminServiceTypeDetailView(APIView):
    """Retrieve, update, or soft-delete a deliverable service template."""
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        try:
            service = ServiceType.objects.select_related('platform').get(id=pk, is_deleted=False)
        except (ServiceType.DoesNotExist, ValueError):
            return Response({'detail': 'Service type not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ServiceTypeSerializer(service)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SETTINGS, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        try:
            service = ServiceType.objects.get(id=pk, is_deleted=False)
        except (ServiceType.DoesNotExist, ValueError):
            return Response({'detail': 'Service type not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ServiceTypeSerializer(service, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        service = serializer.save()
        record_audit_log(
            admin=request.user,
            action='UPDATE_SERVICE_TYPE',
            entity='ServiceType',
            entity_id=str(service.id),
            request=request,
            reason=f"Updated deliverable service {service.name}"
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SETTINGS, 'MANAGE')
    def delete(self, request, pk, *args, **kwargs):
        try:
            service = ServiceType.objects.get(id=pk, is_deleted=False)
        except (ServiceType.DoesNotExist, ValueError):
            return Response({'detail': 'Service type not found.'}, status=status.HTTP_404_NOT_FOUND)

        service.soft_delete()
        record_audit_log(
            admin=request.user,
            action='DELETE_SERVICE_TYPE',
            entity='ServiceType',
            entity_id=str(service.id),
            request=request,
            reason=f"Soft deleted deliverable service {service.name}"
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminDashboardStatsView(APIView):
    """
    Consolidated administrative dashboard overview metrics and analytics aggregator.
    Serves primary platform KPIs, user growth trends, and category distribution.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        Aggregate and return platform operational health and volume indicators.

        :param request: Authenticated administrative HTTP request.
        :return: JSON structured response with top stats, growth series, and category breakdown.
        """
        from datetime import datetime, timedelta
        from django.utils import timezone
        from apps.creators.models import CreatorProfile, VerificationStatus, ProfileStatus
        from apps.businesses.models import BusinessProfile, BusinessStatus
        from apps.campaigns.models import Campaign, CampaignStatus
        from apps.websites.models import CreatorWebsite
        from apps.billing.models import Payment, PaymentStatus
        from apps.taxonomies.models import Category

        now = timezone.now()

        # -----------------------------------------------------------------
        # 1. Core Platform Volume Metrics
        # -----------------------------------------------------------------
        total_influencers = CreatorProfile.objects.filter(is_deleted=False).count()
        active_influencers = CreatorProfile.objects.filter(is_deleted=False, status=ProfileStatus.ACTIVE).count()
        total_businesses = BusinessProfile.objects.filter(is_deleted=False).count()
        active_businesses = BusinessProfile.objects.filter(is_deleted=False, status=BusinessStatus.ACTIVE).count()
        active_campaigns = Campaign.objects.filter(
            is_deleted=False,
            status__in=[CampaignStatus.PUBLISHED, CampaignStatus.APPLICATIONS, CampaignStatus.ACTIVE]
        ).count()
        total_websites = CreatorWebsite.objects.filter(is_deleted=False).count()

        # Monthly revenue calculation (cents / base currency)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        from django.db.models import Sum
        monthly_rev_cents = Payment.objects.filter(
            status=PaymentStatus.PAID,
            created_at__gte=month_start,
            is_deleted=False
        ).aggregate(total=Sum('amount_cents'))['total'] or 0

        # Pending actionable requests count
        pending_verifications = CreatorProfile.objects.filter(
            verification_status=VerificationStatus.PENDING,
            is_deleted=False
        ).count()
        pending_platforms = PlatformRequest.objects.filter(
            status='PENDING',
            is_deleted=False
        ).count()
        pending_requests = pending_verifications + pending_platforms

        # -----------------------------------------------------------------
        # 2. 6-Month User Growth Trends
        # -----------------------------------------------------------------
        months_labels = []
        user_growth = []
        campaign_activity = []

        for i in range(5, -1, -1):
            target_date = now - timedelta(days=i * 30)
            month_name = target_date.strftime("%b")
            start_m = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if target_date.month == 12:
                end_m = target_date.replace(year=target_date.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                end_m = target_date.replace(month=target_date.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

            inf_c = CreatorProfile.objects.filter(created_at__gte=start_m, created_at__lt=end_m).count()
            biz_c = BusinessProfile.objects.filter(created_at__gte=start_m, created_at__lt=end_m).count()
            camp_created = Campaign.objects.filter(created_at__gte=start_m, created_at__lt=end_m).count()
            camp_active = Campaign.objects.filter(status=CampaignStatus.ACTIVE, created_at__gte=start_m, created_at__lt=end_m).count()

            user_growth.append({
                'month': month_name,
                'influencers': inf_c,
                'businesses': biz_c,
            })
            campaign_activity.append({
                'month': month_name,
                'created': camp_created,
                'active': camp_active,
                'completed': Campaign.objects.filter(status=CampaignStatus.COMPLETED, created_at__gte=start_m, created_at__lt=end_m).count()
            })

        # -----------------------------------------------------------------
        # 3. Category Distribution
        # -----------------------------------------------------------------
        top_categories = []
        for cat in Category.objects.filter(is_deleted=False)[:8]:
            top_categories.append({
                'name': cat.name,
                'value': cat.creator_links.count()
            })

        payload = {
            'totalInfluencers': total_influencers,
            'activeInfluencers': active_influencers,
            'totalBusinesses': total_businesses,
            'activeBusinesses': active_businesses,
            'activeCampaigns': active_campaigns,
            'totalWebsites': total_websites,
            'monthlyRevenue': monthly_rev_cents,
            'pendingRequests': pending_requests,
            'userGrowth': user_growth,
            'campaignActivity': campaign_activity,
            'categoryDistribution': top_categories,
        }

        return Response(payload, status=status.HTTP_200_OK)


class AdminMediaAssetListView(APIView):
    """
    Administrative overview of portfolio media assets, avatars, and campaign files (REQ-ADM-01).
    Enforces strict RBAC via ModuleChoice.MEDIA.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.MEDIA, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        List media assets with optional search and type filtering.
        """
        from django.db.models import Q
        from apps.common.models import MediaAsset
        from apps.common.api.v1.serializers import MediaAssetSerializer

        qs = MediaAsset.objects.select_related('uploader').filter(is_deleted=False)

        # Type filter
        file_type = request.query_params.get('type') or request.query_params.get('file_type')
        if file_type and file_type.upper() != 'ALL':
            qs = qs.filter(file_type=file_type.upper())

        # Search filter
        search = request.query_params.get('search')
        if search:
            clean_search = search.strip()
            qs = qs.filter(
                Q(file_name__icontains=clean_search) |
                Q(uploader__email__icontains=clean_search) |
                Q(uploader__username__icontains=clean_search)
            )

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = MediaAssetSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = MediaAssetSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminMediaAssetDetailView(APIView):
    """
    Administrative detail and moderation/deletion for individual media assets (REQ-ADM-01).
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.MEDIA, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        """
        Retrieve details of a specific media asset.
        """
        from apps.common.models import MediaAsset
        from apps.common.api.v1.serializers import MediaAssetSerializer

        try:
            asset = MediaAsset.objects.select_related('uploader').get(id=pk, is_deleted=False)
        except (MediaAsset.DoesNotExist, ValueError):
            return Response({'detail': 'Media asset not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = MediaAssetSerializer(asset)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.MEDIA, 'MANAGE')
    def delete(self, request, pk, *args, **kwargs):
        """
        Soft-delete a media asset and record compliance audit log.
        """
        from django.db import transaction
        from apps.common.models import MediaAsset
        from apps.common.api.v1.services import record_audit_log

        try:
            asset = MediaAsset.objects.get(id=pk, is_deleted=False)
        except (MediaAsset.DoesNotExist, ValueError):
            return Response({'detail': 'Media asset not found.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            asset.is_deleted = True
            asset.save(update_fields=['is_deleted', 'updated_at'])

            record_audit_log(
                admin=request.user,
                action='DELETE_MEDIA_ASSET',
                entity='MediaAsset',
                entity_id=str(asset.id),
                request=request,
                reason=f"Administrator removed media asset: {asset.file_name} ({asset.file_type})"
            )

        return Response({'status': 'deleted', 'id': str(pk)}, status=status.HTTP_200_OK)

