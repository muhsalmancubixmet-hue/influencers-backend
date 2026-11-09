from django.contrib import admin
from apps.creators.models import (
    CreatorProfile,
    CreatorCategory,
    CreatorLanguage,
    CreatorServiceArea,
    SocialAccount,
    PortfolioItem,
    CreatorService
)


class CreatorCategoryInline(admin.TabularInline):
    model = CreatorCategory
    extra = 1


class SocialAccountInline(admin.TabularInline):
    model = SocialAccount
    extra = 1


class CreatorServiceInline(admin.TabularInline):
    model = CreatorService
    extra = 1


@admin.register(CreatorProfile)
class CreatorProfileAdmin(admin.ModelAdmin):
    """Administrative representation for Creator and Influencer profiles."""
    list_display = ('handle', 'display_name', 'get_email', 'status', 'verification_status', 'created_at')
    list_filter = ('status', 'verification_status')
    search_fields = ('handle', 'display_name', 'user__email')
    ordering = ('-created_at',)
    inlines = [CreatorCategoryInline, SocialAccountInline, CreatorServiceInline]
    readonly_fields = ('created_at', 'updated_at')

    def get_email(self, obj) -> str:
        return obj.user.email if obj.user else '-'
    get_email.short_description = 'Email'


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    """Connected external social network accounts."""
    list_display = ('creator', 'platform', 'username', 'followers_count', 'is_verified', 'created_at')
    list_filter = ('platform', 'is_verified')
    search_fields = ('creator__handle', 'creator__display_name', 'username')


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    """Creator showcase portfolio assets."""
    list_display = ('creator', 'title', 'media_type', 'order', 'created_at')
    list_filter = ('media_type',)
    search_fields = ('creator__handle', 'title')


@admin.register(CreatorService)
class CreatorServiceAdmin(admin.ModelAdmin):
    """Custom deliverable rate card packages sold by creators."""
    list_display = ('creator', 'name', 'starting_price_cents', 'currency', 'is_active', 'created_at')
    list_filter = ('is_active', 'currency')
    search_fields = ('creator__handle', 'name')
