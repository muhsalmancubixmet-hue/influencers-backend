from django.urls import path
from apps.campaigns.api.v1.views import (
    AdminCampaignListView,
    AdminCampaignDetailView,
    AdminRequirementListView,
    AdminRequirementDetailView,
    CreatorOpportunitiesListView,
    CreatorOpportunityApplyView,
    CreatorInquiryListView,
    CreatorInquiryDetailView,
    CreatorInquiryMessagesView,
    CreatorInquiryMarkReadView,
    PublicCampaignListView,
    PublicInquiryCreateView
)

urlpatterns = [
    # Public marketplace endpoints
    path('public/campaigns/', PublicCampaignListView.as_view(), name='public_campaigns_list'),
    path('public/inquiries/', PublicInquiryCreateView.as_view(), name='public_inquiry_create'),

    # Creator Marketplace & Inquiries
    path('creator/opportunities/', CreatorOpportunitiesListView.as_view(), name='creator_opportunities_list'),
    path('creator/opportunities/<uuid:pk>/apply/', CreatorOpportunityApplyView.as_view(), name='creator_opportunity_apply'),
    path('creator/inquiries/', CreatorInquiryListView.as_view(), name='creator_inquiries_list'),
    path('creator/inquiries/<uuid:pk>/', CreatorInquiryDetailView.as_view(), name='creator_inquiry_detail'),
    path('creator/inquiries/<uuid:pk>/messages/', CreatorInquiryMessagesView.as_view(), name='creator_inquiry_messages'),
    path('creator/inquiries/<uuid:pk>/read/', CreatorInquiryMarkReadView.as_view(), name='creator_inquiry_mark_read'),

    # Admin Campaigns & Requirements
    path('admin/campaigns/', AdminCampaignListView.as_view(), name='admin_campaigns_list'),
    path('admin/campaigns/<uuid:pk>/', AdminCampaignDetailView.as_view(), name='admin_campaigns_detail'),
    path('admin/requirements/', AdminRequirementListView.as_view(), name='admin_requirements_list'),
    path('admin/requirements/<uuid:pk>/', AdminRequirementDetailView.as_view(), name='admin_requirements_detail'),
]
