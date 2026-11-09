from django.contrib import admin
from apps.campaigns.models import (
    Campaign,
    Requirement,
    CampaignBid,
    Inquiry
)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Administrative representation for marketplace Campaigns."""
    list_display = ('title', 'business', 'status', 'escrow_status', 'total_budget_cents', 'is_featured', 'created_at')
    list_filter = ('status', 'escrow_status', 'is_featured')
    search_fields = ('title', 'business__company_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    """Public creator requirement board leads."""
    list_display = ('title', 'business', 'status', 'category', 'creators_needed', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('title', 'business__company_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CampaignBid)
class CampaignBidAdmin(admin.ModelAdmin):
    """Creator applications and quotation bids on campaigns."""
    list_display = ('campaign', 'creator', 'status', 'proposed_fee_cents', 'match_percentage', 'created_at')
    list_filter = ('status',)
    search_fields = ('campaign__title', 'creator__handle')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    """Direct business-to-creator inquiries."""
    list_display = ('subject', 'business', 'creator', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('subject', 'business__company_name', 'creator__handle')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
