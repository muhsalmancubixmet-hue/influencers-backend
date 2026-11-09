from django.contrib import admin
from apps.websites.models import CreatorWebsite, WebsiteSection, DomainRecord


@admin.register(CreatorWebsite)
class CreatorWebsiteAdmin(admin.ModelAdmin):
    list_display = ('subdomain', 'creator', 'template', 'status', 'is_published', 'visitors_count', 'created_at')
    list_filter = ('status', 'template', 'is_published')
    search_fields = ('subdomain', 'title', 'creator__handle', 'creator__display_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WebsiteSection)
class WebsiteSectionAdmin(admin.ModelAdmin):
    list_display = ('section_name', 'website', 'order', 'is_enabled', 'created_at')
    list_filter = ('section_name', 'is_enabled')
    search_fields = ('section_name', 'website__subdomain')
    ordering = ('website', 'order')


@admin.register(DomainRecord)
class DomainRecordAdmin(admin.ModelAdmin):
    list_display = ('domain', 'website', 'domain_type', 'verification_status', 'ssl_status', 'verified_at')
    list_filter = ('domain_type', 'verification_status', 'ssl_status')
    search_fields = ('domain', 'website__subdomain', 'dns_txt_token')
    readonly_fields = ('dns_txt_token', 'last_checked_at', 'verified_at', 'created_at', 'updated_at')

