from rest_framework import serializers

from apps.common.models import (
    SocialPlatform,
    PlatformRequest,
    PlatformRequestStatus,
    ServiceType,
    PlatformSetting,
    MediaAsset,
    SupportTicket,
    TicketMessage,
    AuditLog,
    Notification
)


class SocialPlatformSerializer(serializers.ModelSerializer):
    """Serializer representing supported social network platform."""

    class Meta:
        model = SocialPlatform
        fields = [
            'id',
            'name',
            'slug',
            'icon_name',
            'color_code',
            'is_active',
            'supports_oauth',
            'supports_api',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class PlatformRequestSerializer(serializers.ModelSerializer):
    """Serializer representing creator platform requests."""
    requested_by_email = serializers.EmailField(source='requested_by.email', read_only=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)

    class Meta:
        model = PlatformRequest
        fields = [
            'id',
            'requested_by',
            'requested_by_email',
            'platform_name',
            'profile_url',
            'note',
            'status',
            'reviewed_by',
            'reviewed_by_email',
            'reviewed_at',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'requested_by',
            'requested_by_email',
            'reviewed_by',
            'reviewed_by_email',
            'reviewed_at',
            'created_at'
        ]


class PlatformRequestReviewSerializer(serializers.Serializer):
    """Payload contract for staff review (approve/reject) of platform petitions."""
    status = serializers.ChoiceField(choices=[PlatformRequestStatus.APPROVED, PlatformRequestStatus.REJECTED])


class PlatformSettingSerializer(serializers.ModelSerializer):
    """Serializer for dynamic platform settings."""

    class Meta:
        model = PlatformSetting
        fields = ['id', 'section', 'key', 'value_json', 'description', 'updated_at']
        read_only_fields = ['id', 'section', 'key', 'updated_at']


class CustomerTicketMessageSerializer(serializers.ModelSerializer):
    """
    Customer-facing serializer for ticket replies.
    Strictly filters out internal staff notes to prevent leaks.
    """
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            'id',
            'author_name',
            'is_staff',
            'body',
            'attachment_url',
            'created_at'
        ]
        read_only_fields = ['id', 'author_name', 'is_staff', 'created_at']


class StaffTicketMessageSerializer(serializers.ModelSerializer):
    """
    Staff-facing serializer for ticket messages, including internal notes.
    """
    author_email = serializers.EmailField(source='author.email', read_only=True)
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            'id',
            'author',
            'author_email',
            'author_name',
            'is_staff',
            'is_internal_note',
            'body',
            'attachment_url',
            'created_at'
        ]
        read_only_fields = ['id', 'author', 'author_email', 'author_name', 'is_staff', 'created_at']


class SupportTicketSerializer(serializers.ModelSerializer):
    """Serializer representing customer support helpdesk ticket."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    assignee_email = serializers.EmailField(source='assignee.email', read_only=True, allow_null=True)
    messages_count = serializers.IntegerField(source='messages.count', read_only=True)
    messages = serializers.IntegerField(source='messages.count', read_only=True)
    user = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()
    updated = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            'id',
            'user',
            'user_email',
            'subject',
            'category',
            'priority',
            'status',
            'assignee',
            'assignee_email',
            'messages',
            'messages_count',
            'created',
            'updated',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'user', 'user_email', 'messages', 'messages_count', 'created_at', 'updated_at']

    def get_user(self, obj):
        name = obj.user.get_full_name()
        return name if name else obj.user.email

    def get_assignee(self, obj):
        if not obj.assignee:
            return "Unassigned"
        name = obj.assignee.get_full_name()
        return name if name else obj.assignee.email

    def get_created(self, obj):
        return obj.created_at.strftime("%b %d, %Y") if obj.created_at else ""

    def get_updated(self, obj):
        return obj.updated_at.strftime("%b %d, %Y") if obj.updated_at else ""

    def get_priority(self, obj):
        return (obj.priority or "medium").lower()

    def get_status(self, obj):
        return (obj.status or "open").lower().replace("_", " ")



class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer representing immutable audit trail entry."""
    admin_email = serializers.EmailField(source='admin.email', read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'admin',
            'admin_email',
            'action',
            'entity',
            'entity_id',
            'ip_address',
            'user_agent',
            'result',
            'reason',
            'created_at'
        ]
        read_only_fields = ['id', 'admin', 'admin_email', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer representing notifications and broadcast announcements."""

    class Meta:
        model = Notification
        fields = [
            'id',
            'recipient',
            'title',
            'message',
            'kind',
            'audience',
            'scheduled_at',
            'status',
            'is_read',
            'created_at'
        ]
        read_only_fields = ['id', 'is_read', 'created_at']


class ServiceTypeSerializer(serializers.ModelSerializer):
    """Serializer representing platform deliverable catalog templates."""
    platform_name = serializers.CharField(source='platform.name', read_only=True, allow_null=True)
    avg_price = serializers.SerializerMethodField()

    class Meta:
        model = ServiceType
        fields = [
            'id',
            'name',
            'platform',
            'platform_name',
            'avg_price_cents',
            'avg_price',
            'currency',
            'deliverables_template',
            'is_active',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'avg_price', 'platform_name']

    def get_avg_price(self, obj) -> float:
        return round((obj.avg_price_cents or 0) / 100.0, 2)

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Parse avg_price / avgPrice input
        raw_price = mutable_data.get('avg_price') if 'avg_price' in mutable_data else mutable_data.get('avgPrice')
        if raw_price is not None:
            try:
                mutable_data['avg_price_cents'] = int(float(raw_price) * 100)
            except (ValueError, TypeError):
                mutable_data['avg_price_cents'] = 0
        elif 'avg_price_cents' not in mutable_data:
            mutable_data['avg_price_cents'] = 0

        # Deliverables spec
        if 'deliverables' in mutable_data and not mutable_data.get('deliverables_template'):
            mutable_data['deliverables_template'] = mutable_data['deliverables']

        if not mutable_data.get('deliverables_template'):
            mutable_data['deliverables_template'] = 'Standard deliverables spec.'

        # Support platform name or UUID
        plat_val = mutable_data.get('platform')
        if plat_val and isinstance(plat_val, str) and plat_val.lower() != 'any':
            import uuid
            plat = None
            try:
                plat_uuid = uuid.UUID(plat_val)
                plat = SocialPlatform.objects.filter(id=plat_uuid, is_deleted=False).first()
            except ValueError:
                plat = SocialPlatform.objects.filter(name__iexact=plat_val, is_deleted=False).first()
            if plat:
                mutable_data['platform'] = str(plat.id)
            else:
                mutable_data.pop('platform', None)
        elif plat_val and isinstance(plat_val, str) and plat_val.lower() == 'any':
            mutable_data.pop('platform', None)

        return super().to_internal_value(mutable_data)


class MediaAssetSerializer(serializers.ModelSerializer):
    """
    Serializer representing digital media assets in the admin library (REQ-ADM-01).
    """
    uploader_name = serializers.SerializerMethodField()
    uploader_email = serializers.EmailField(source='uploader.email', read_only=True)
    size_kb = serializers.SerializerMethodField()

    class Meta:
        model = MediaAsset
        fields = [
            'id',
            'file_name',
            'file_type',
            'file_size_bytes',
            'size_kb',
            'cdn_url',
            'mime_type',
            'uploader',
            'uploader_name',
            'uploader_email',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_uploader_name(self, obj: MediaAsset) -> str:
        if not obj.uploader:
            return "System"
        return obj.uploader.get_full_name() or obj.uploader.username

    def get_size_kb(self, obj: MediaAsset) -> int:
        if not obj.file_size_bytes:
            return 0
        return round(obj.file_size_bytes / 1024)

