from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api.v1.views import (
    CustomTokenObtainPairView,
    RoleTemplateListView,
    StaffListCreateView,
    StaffDetailView,
    StaffInvitationListView,
    StaffInviteAcceptView,
    StaffInviteRevokeView,
    CreatorRegistrationView,
    EmailVerificationView,
    RevokeRegistrationView,
    PasswordChangeView,
    MfaToggleView,
    AccountDeleteView
)

urlpatterns = [
    # Auth & Account management endpoints
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='auth_token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='auth_token_refresh'),
    path('auth/creator/register/', CreatorRegistrationView.as_view(), name='auth_creator_register'),
    path('auth/verify-email/', EmailVerificationView.as_view(), name='auth_verify_email'),
    path('auth/revoke-registration/', RevokeRegistrationView.as_view(), name='auth_revoke_registration'),
    path('auth/password/change/', PasswordChangeView.as_view(), name='auth_password_change'),
    path('auth/mfa/toggle/', MfaToggleView.as_view(), name='auth_mfa_toggle'),
    path('auth/account/delete/', AccountDeleteView.as_view(), name='auth_account_delete'),
    path('auth/staff/invite/accept/', StaffInviteAcceptView.as_view(), name='auth_staff_invite_accept'),
    path('auth/staff/invite/revoke/', StaffInviteRevokeView.as_view(), name='auth_staff_invite_revoke'),

    # Admin Staff & RBAC endpoints
    path('admin/accounts/staff/', StaffListCreateView.as_view(), name='admin_staff_list_create'),
    path('admin/accounts/staff/invitations/', StaffInvitationListView.as_view(), name='admin_staff_invitations_list'),
    path('admin/accounts/staff/<uuid:pk>/', StaffDetailView.as_view(), name='admin_staff_detail'),
    path('admin/accounts/role-templates/', RoleTemplateListView.as_view(), name='admin_role_templates_list'),
]

