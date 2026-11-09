from django.urls import path
from apps.websites.api.v1.views import (
    CreatorWebsiteView,
    CreatorWebsiteDomainView,
    AdminDomainListView,
    AdminDomainVerifyView,
    AdminWebsiteListView,
    AdminWebsiteDetailView
)

urlpatterns = [
    # Creator website & domain builder
    path('creator/website/', CreatorWebsiteView.as_view(), name='creator_website'),
    path('creator/website/domain/', CreatorWebsiteDomainView.as_view(), name='creator_website_domain'),

    # Admin custom domain management & DNS verification
    path('admin/domains/', AdminDomainListView.as_view(), name='admin_domains_list'),
    path('admin/domains/<uuid:pk>/verify-dns/', AdminDomainVerifyView.as_view(), name='admin_domains_verify_dns'),

    # Admin website moderation
    path('admin/websites/', AdminWebsiteListView.as_view(), name='admin_websites_list'),
    path('admin/websites/<uuid:pk>/', AdminWebsiteDetailView.as_view(), name='admin_websites_detail'),
]
