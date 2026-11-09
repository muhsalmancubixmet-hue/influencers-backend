from rest_framework import serializers

from apps.websites.models import (
    CreatorWebsite,
    WebsiteSection,
    DomainRecord,
    WebsiteStatus,
    WebsiteTemplate
)


class WebsiteSectionSerializer(serializers.ModelSerializer):
    """Serializer representing modular website section."""

    class Meta:
        model = WebsiteSection
        fields = [
            'id',
            'section_name',
            'is_enabled',
            'order',
            'config_json'
        ]
        read_only_fields = ['id']


class DomainRecordSerializer(serializers.ModelSerializer):
    """Serializer representing custom domain mapping with verification status."""

    class Meta:
        model = DomainRecord
        fields = [
            'id',
            'domain',
            'domain_type',
            'verification_status',
            'ssl_status',
            'dns_txt_token',
            'last_checked_at',
            'verified_at',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'domain_type',
            'verification_status',
            'ssl_status',
            'dns_txt_token',
            'last_checked_at',
            'verified_at',
            'created_at'
        ]


class CreatorWebsiteSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for creator website configuration and modular sections."""
    sections = WebsiteSectionSerializer(many=True, read_only=True)
    domain_records = DomainRecordSerializer(many=True, read_only=True)
    full_url = serializers.SerializerMethodField()

    class Meta:
        model = CreatorWebsite
        fields = [
            'id',
            'template',
            'title',
            'tagline',
            'subdomain',
            'full_url',
            'accent_color',
            'font_family',
            'layout_style',
            'status',
            'is_published',
            'published_at',
            'external_url',
            'visitors_count',
            'sections',
            'domain_records',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'full_url',
            'status',
            'published_at',
            'visitors_count',
            'created_at'
        ]

    def get_full_url(self, obj):
        return f"https://{obj.subdomain}.influencers.site"


class ConnectCustomDomainSerializer(serializers.Serializer):
    """Payload contract for connecting a custom apex or subdomain."""
    domain = serializers.CharField(max_length=255)


class AdminWebsiteSerializer(serializers.ModelSerializer):
    """Administrative representation of creator websites for platform moderation."""
    creator_name = serializers.CharField(source='creator.display_name', read_only=True)
    creator_handle = serializers.CharField(source='creator.handle', read_only=True)
    creator_avatar = serializers.CharField(source='creator.photo_url', read_only=True)
    custom_domain = serializers.SerializerMethodField()
    full_url = serializers.SerializerMethodField()

    class Meta:
        model = CreatorWebsite
        fields = [
            'id',
            'creator',
            'creator_name',
            'creator_handle',
            'creator_avatar',
            'title',
            'subdomain',
            'full_url',
            'custom_domain',
            'template',
            'status',
            'is_published',
            'visitors_count',
            'created_at'
        ]

    def get_full_url(self, obj):
        return f"https://{obj.subdomain}.influencers.site"

    def get_custom_domain(self, obj):
        rec = obj.domain_records.filter(verification_status='VERIFIED', is_deleted=False).first()
        return rec.domain if rec else None
