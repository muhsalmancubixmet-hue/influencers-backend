from django.contrib import admin
from apps.common.models import (
    SocialPlatform,
    PlatformRequest,
    ServiceType,
    PlatformSetting,
    MediaAsset,
    SupportTicket,
    TicketMessage,
    AuditLog,
    Notification
)


@admin.register(SocialPlatform)
class SocialPlatformAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color_code', 'is_active', 'supports_oauth', 'supports_api')
    list_filter = ('is_active', 'supports_oauth', 'supports_api')
    search_fields = ('name', 'slug')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PlatformRequest)
class PlatformRequestAdmin(admin.ModelAdmin):
    list_display = ('platform_name', 'requested_by', 'status', 'reviewed_by', 'reviewed_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('platform_name', 'requested_by__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'platform', 'avg_price_cents', 'currency', 'is_active')
    list_filter = ('is_active', 'platform')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'section', 'created_at', 'updated_at')
    list_filter = ('section',)
    search_fields = ('key', 'section')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'uploader', 'file_type', 'file_size_bytes', 'mime_type', 'created_at')
    list_filter = ('file_type',)
    search_fields = ('file_name', 'uploader__email')
    readonly_fields = ('created_at', 'updated_at')


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ('author', 'is_staff', 'is_internal_note', 'body', 'created_at')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'user', 'category', 'priority', 'status', 'assignee', 'created_at')
    list_filter = ('category', 'priority', 'status')
    search_fields = ('subject', 'user__email', 'assignee__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [TicketMessageInline]


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'author', 'is_staff', 'is_internal_note', 'created_at')
    list_filter = ('is_staff', 'is_internal_note')
    search_fields = ('author__email', 'ticket__subject', 'body')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'entity', 'entity_id', 'admin', 'result', 'ip_address', 'created_at')
    list_filter = ('action', 'entity', 'result')
    search_fields = ('action', 'entity', 'entity_id', 'admin__email', 'reason')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'audience', 'kind', 'status', 'is_read', 'created_at')
    list_filter = ('kind', 'status', 'is_read')
    search_fields = ('title', 'message', 'recipient__email', 'audience')
    readonly_fields = ('created_at', 'updated_at')
