from django.urls import path
from apps.creators.api.v1.views import (
    CreatorProfileView,
    CreatorPortfolioListCreateView,
    CreatorPortfolioDetailView,
    CreatorPortfolioReorderView,
    CreatorServiceListCreateView,
    CreatorServiceDetailView,
    CreatorMediaUploadView,
    CreatorSocialPlatformListView,
    CreatorSocialAccountListCreateView,
    CreatorSocialAccountDetailView,
    CreatorPlatformRequestCreateView,
    AdminInfluencerListView,
    AdminInfluencerDetailView,
    PublicCreatorListView,
    PublicCreatorDetailView
)

urlpatterns = [
    # Public marketplace endpoints
    path('public/creators/', PublicCreatorListView.as_view(), name='public_creators_list'),
    path('public/creators/<str:slug>/', PublicCreatorDetailView.as_view(), name='public_creators_detail'),

    # Creator workspace endpoints
    path('creator/profile/', CreatorProfileView.as_view(), name='creator_profile'),
    path('creator/media/upload/', CreatorMediaUploadView.as_view(), name='creator_media_upload'),
    path('creator/portfolio/', CreatorPortfolioListCreateView.as_view(), name='creator_portfolio_list_create'),
    path('creator/portfolio/reorder/', CreatorPortfolioReorderView.as_view(), name='creator_portfolio_reorder'),
    path('creator/portfolio/<uuid:pk>/', CreatorPortfolioDetailView.as_view(), name='creator_portfolio_detail'),
    path('creator/services/', CreatorServiceListCreateView.as_view(), name='creator_services_list_create'),
    path('creator/services/<uuid:pk>/', CreatorServiceDetailView.as_view(), name='creator_services_detail'),
    path('creator/social-platforms/', CreatorSocialPlatformListView.as_view(), name='creator_social_platforms_list'),
    path('creator/social-platforms/request/', CreatorPlatformRequestCreateView.as_view(), name='creator_social_platforms_request'),
    path('creator/social-accounts/', CreatorSocialAccountListCreateView.as_view(), name='creator_social_accounts_list_create'),
    path('creator/social-accounts/<uuid:pk>/', CreatorSocialAccountDetailView.as_view(), name='creator_social_accounts_detail'),

    # Admin Control Panel endpoints
    path('admin/influencers/', AdminInfluencerListView.as_view(), name='admin_influencers_list'),
    path('admin/influencers/<uuid:pk>/', AdminInfluencerDetailView.as_view(), name='admin_influencers_detail'),
]

