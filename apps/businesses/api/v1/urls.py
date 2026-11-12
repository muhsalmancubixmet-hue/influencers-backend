from django.urls import path
from apps.businesses.api.v1.views import (
    AdminBusinessListView,
    AdminBusinessDetailView,
    BusinessRegistrationView,
    BusinessSelfProfileView,
    BusinessVerificationApplyView,
    BusinessOperatingLocationListCreateView,
    BusinessOperatingLocationDetailView,
    BusinessCampaignListCreateView,
    BusinessCampaignDetailView,
    BusinessCampaignApplicationsView,
    BusinessRequirementListCreateView,
    BusinessRequirementDetailView,
    BusinessInquiryListView,
    BusinessInquiryMessagesView,
    BusinessInquiriesUnreadCountView,
    BusinessDashboardStatsView,
    BusinessShortlistListCreateView,
    BusinessShortlistDetailView,
    BusinessShortlistCreatorManageView,
    BusinessShortlistToggleView,
    BusinessSavedSearchListCreateView,
    BusinessSavedSearchDetailView,
    BusinessSavedSearchToggleNotifyView,
    BusinessAnalyticsView,
    BusinessMediaUploadView,
)

urlpatterns = [
    # Admin Control Panel business management endpoints
    path('admin/businesses/', AdminBusinessListView.as_view(), name='admin_businesses_list'),
    path('admin/businesses/<uuid:pk>/', AdminBusinessDetailView.as_view(), name='admin_businesses_detail'),

    # Brand / Business Portal Client Endpoints
    path('business/register/', BusinessRegistrationView.as_view(), name='business_register'),
    path('auth/business/register/', BusinessRegistrationView.as_view(), name='auth_business_register'),
    path('business/profile/', BusinessSelfProfileView.as_view(), name='business_self_profile'),
    path('business/verification/apply/', BusinessVerificationApplyView.as_view(), name='business_verification_apply'),
    path('business/operating-locations/', BusinessOperatingLocationListCreateView.as_view(), name='business_operating_locations_list_create'),
    path('business/operating-locations/<uuid:pk>/', BusinessOperatingLocationDetailView.as_view(), name='business_operating_location_detail'),
    path('business/campaigns/', BusinessCampaignListCreateView.as_view(), name='business_campaigns_list_create'),
    path('business/campaigns/<uuid:pk>/', BusinessCampaignDetailView.as_view(), name='business_campaigns_detail'),
    path('business/campaigns/<uuid:pk>/applications/', BusinessCampaignApplicationsView.as_view(), name='business_campaign_applications_list'),
    path('business/campaigns/<uuid:pk>/applications/<uuid:bid_id>/', BusinessCampaignApplicationsView.as_view(), name='business_campaign_application_update'),
    path('business/requirements/', BusinessRequirementListCreateView.as_view(), name='business_requirements_list_create'),
    path('business/requirements/<uuid:pk>/', BusinessRequirementDetailView.as_view(), name='business_requirements_detail'),
    path('business/inquiries/', BusinessInquiryListView.as_view(), name='business_inquiries_list'),
    path('business/inquiries/unread-count/', BusinessInquiriesUnreadCountView.as_view(), name='business_inquiries_unread_count'),
    path('business/inquiries/<uuid:pk>/messages/', BusinessInquiryMessagesView.as_view(), name='business_inquiry_messages'),
    path('business/dashboard/stats/', BusinessDashboardStatsView.as_view(), name='business_dashboard_stats'),
    path('business/media/upload/', BusinessMediaUploadView.as_view(), name='business_media_upload'),

    # Shortlists Management Endpoints
    path('business/shortlists/', BusinessShortlistListCreateView.as_view(), name='business_shortlists_list_create'),
    path('business/shortlists/<uuid:pk>/', BusinessShortlistDetailView.as_view(), name='business_shortlist_detail'),
    path('business/shortlists/<uuid:pk>/creators/', BusinessShortlistCreatorManageView.as_view(), name='business_shortlist_creator_add'),
    path('business/shortlists/<uuid:pk>/creators/<uuid:creator_id>/', BusinessShortlistCreatorManageView.as_view(), name='business_shortlist_creator_remove'),
    path('business/shortlists/toggle/', BusinessShortlistToggleView.as_view(), name='business_shortlist_toggle'),
    # Analytics Endpoint
    path('business/analytics/', BusinessAnalyticsView.as_view(), name='business_analytics'),

    # Saved Searches Management Endpoints
    path('business/saved-searches/', BusinessSavedSearchListCreateView.as_view(), name='business_saved_searches_list_create'),
    path('business/saved-searches/<uuid:pk>/', BusinessSavedSearchDetailView.as_view(), name='business_saved_searches_detail'),
    path('business/saved-searches/<uuid:pk>/toggle-notify/', BusinessSavedSearchToggleNotifyView.as_view(), name='business_saved_searches_toggle_notify'),
]
