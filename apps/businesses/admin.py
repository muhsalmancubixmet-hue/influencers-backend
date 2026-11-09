from django.contrib import admin
from apps.businesses.models import (
    BusinessProfile,
    BusinessShortlist,
    ShortlistEntry,
    BusinessSavedSearch
)


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    """Administrative representation for Brand & Business profiles."""
    list_display = ('company_name', 'get_email', 'business_type', 'verification_status', 'status', 'created_at')
    list_filter = ('business_type', 'verification_status', 'status')
    search_fields = ('company_name', 'user__email')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    def get_email(self, obj) -> str:
        return obj.user.email if obj.user else '-'
    get_email.short_description = 'Account Email'


class ShortlistEntryInline(admin.TabularInline):
    model = ShortlistEntry
    extra = 0
    raw_id_fields = ('creator',)


@admin.register(BusinessShortlist)
class BusinessShortlistAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'entries_count', 'color', 'is_archived', 'created_at')
    list_filter = ('is_archived', 'color')
    search_fields = ('name', 'business__company_name')
    inlines = [ShortlistEntryInline]

    def entries_count(self, obj):
        return obj.entries.count()
    entries_count.short_description = 'Creators'


@admin.register(ShortlistEntry)
class ShortlistEntryAdmin(admin.ModelAdmin):
    list_display = ('shortlist', 'creator', 'created_at')
    search_fields = ('shortlist__name', 'creator__handle', 'creator__display_name')


@admin.register(BusinessSavedSearch)
class BusinessSavedSearchAdmin(admin.ModelAdmin):
    """Administrative representation for brand saved searches."""
    list_display = ('name', 'business', 'notify_enabled', 'new_matches_count', 'created_at')
    list_filter = ('notify_enabled',)
    search_fields = ('name', 'business__company_name')
    readonly_fields = ('created_at', 'updated_at')


