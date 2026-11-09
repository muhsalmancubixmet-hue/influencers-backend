from django.urls import path
from apps.common.api.v1.views import (
    AdminSocialPlatformListCreateView,
    AdminSocialPlatformDetailView,
    AdminPlatformRequestListView,
    AdminPlatformRequestReviewView,
    AdminPlatformSettingListView,
    AdminPlatformSettingDetailView,
    AdminSupportTicketListView,
    AdminSupportTicketDetailView,
    AdminSupportTicketMessagesView,
    AdminAuditLogListView,
    AdminNotificationListCreateView,
    AdminVerificationQueueView,
    CreatorNotificationListView,
    BusinessNotificationListView,
    NotificationMarkReadView,
    AdminDashboardStatsView,
    AdminServiceTypeListCreateView,
    AdminServiceTypeDetailView
)

urlpatterns = [
    # Admin Executive Dashboard Overview
    path('admin/dashboard/stats/', AdminDashboardStatsView.as_view(), name='admin_dashboard_stats'),
    path('admin/verification/queue/', AdminVerificationQueueView.as_view(), name='admin_verification_queue'),

    # Admin Social platforms & petitions
    path('admin/social-platforms/', AdminSocialPlatformListCreateView.as_view(), name='admin_social_platforms_list_create'),
    path('admin/social-platforms/<uuid:pk>/', AdminSocialPlatformDetailView.as_view(), name='admin_social_platforms_detail'),
    path('admin/social-platforms/requests/', AdminPlatformRequestListView.as_view(), name='admin_platform_requests_list'),
    path('admin/social-platforms/requests/<uuid:pk>/review/', AdminPlatformRequestReviewView.as_view(), name='admin_platform_requests_review'),

    # Admin Creator Service Types
    path('admin/service-types/', AdminServiceTypeListCreateView.as_view(), name='admin_service_types_list_create'),
    path('admin/service-types/<uuid:pk>/', AdminServiceTypeDetailView.as_view(), name='admin_service_types_detail'),

    # Admin Dynamic Settings
    path('admin/settings/', AdminPlatformSettingListView.as_view(), name='admin_settings_list'),
    path('admin/settings/<str:key>/', AdminPlatformSettingDetailView.as_view(), name='admin_settings_detail'),

    # Admin Support Helpdesk
    path('admin/support/', AdminSupportTicketListView.as_view(), name='admin_support_list_alias'),
    path('admin/support/<uuid:pk>/', AdminSupportTicketDetailView.as_view(), name='admin_support_detail_alias'),
    path('admin/support/<uuid:pk>/messages/', AdminSupportTicketMessagesView.as_view(), name='admin_support_messages_alias'),
    path('admin/support/tickets/', AdminSupportTicketListView.as_view(), name='admin_support_tickets_list'),
    path('admin/support/tickets/<uuid:pk>/', AdminSupportTicketDetailView.as_view(), name='admin_support_tickets_detail'),
    path('admin/support/tickets/<uuid:pk>/messages/', AdminSupportTicketMessagesView.as_view(), name='admin_support_tickets_messages'),

    # Admin Compliance & Broadcast
    path('admin/audit-logs/', AdminAuditLogListView.as_view(), name='admin_audit_logs_list'),
    path('admin/notifications/', AdminNotificationListCreateView.as_view(), name='admin_notifications_list_create'),

    # Creator & Business Notification Feed
    path('creator/notifications/', CreatorNotificationListView.as_view(), name='creator_notifications_list'),
    path('creator/notifications/<uuid:pk>/read/', NotificationMarkReadView.as_view(), name='creator_notifications_mark_read'),
    path('business/notifications/', BusinessNotificationListView.as_view(), name='business_notifications_list'),
    path('business/notifications/<uuid:pk>/read/', NotificationMarkReadView.as_view(), name='business_notifications_mark_read'),
]
