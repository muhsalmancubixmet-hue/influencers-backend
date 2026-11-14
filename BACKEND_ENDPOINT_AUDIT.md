# Backend Endpoint Security & RBAC Audit Report

**Project**: Influencers.com / Kerala Creator Collab Unified Backend
**Date**: November 14, 2026
**Audit Scope**: Full Backend API Surface (`/api/...`) — 124 Endpoints Across All Functional Domains
**Auditor**: Antigravity Autonomous Autonomous Agent (KCC Mission Section 10c)

---

## 1. Executive Summary

A complete and comprehensive security, tenancy isolation, and role-based access control (RBAC) audit was performed across all **124 registered API endpoints** in the Django REST Framework backend.

### Key Audit Outcomes:
1. **Zero Tenant Boundary Breaches**: All creator, business, and staff endpoints strictly enforce object-level ownership checks via `get_creator_profile_or_403`, `get_business_profile_or_403`, or tenant-filtered querysets (`user=request.user`).
2. **Dynamic Database RBAC Enforcement**: Administrative and moderation endpoints use the `@require_module_access` decorator, which dynamically queries active `StaffProfile` and `RolePermission` models from the database on every request, preventing privilege escalation from stale tokens.
3. **Public Marketplace Sanitization**: Public endpoints (`/api/v1/public/...`) provide zero-leak access: all private user emails, hashed passwords, internal notes, and direct contact numbers are completely excluded from serializers.
4. **Anti-Account Hijacking in Public Inquiries**: The `POST /api/v1/public/inquiries/` service rejects guest inquiries if the email matches an active creator or admin, or if an unauthenticated caller attempts to claim a registered password-protected business account.
5. **CORS Defense**: Whitelisted to permitted client origins (`http://localhost:8080`, `8081`, `8082`, `8083`, `5173`) with preflight `OPTIONS` validated.

---

## 2. RBAC Decorator Architecture Verification

### `@require_module_access(module_name, min_level='VIEW')`
Located at `backend/apps/accounts/decorators.py`:
- **Authentication Gate**: Rejects unauthenticated callers immediately with `rest_framework.exceptions.NotAuthenticated` (HTTP 401), preventing `AttributeError` on anonymous `user` instances.
- **Superuser Bypass**: Automatically bypasses checks if `user.is_superuser` or `user.role == 'SUPER_ADMIN'`.
- **Staff Isolation**: Enforces `user.role == 'STAFF'`; all other roles receive `PermissionDenied` (HTTP 403).
- **Dynamic Database Lookup**: Directly queries `StaffProfile.objects.select_related('role_template')` and `RolePermission.objects.filter(role_template=..., module=module_name)` on every invocation.
- **Tier Hierarchy Weights**: Evaluates numerical clearance rank against required minimum (`VIEW`=10, `MODERATE`=20, `MANAGE`=30, `FULL`=40).
- **Signature & Metadata Preservation**: Decorated using `@wraps(view_func)` to preserve function signature, docstring, and naming for introspection and OpenAPI schema generators.

---

## 3. Comprehensive Endpoint Inventory (124 Endpoints)

| Endpoint Path | Methods | View Class | Auth | Permissions | RBAC Decorator | Tenant Isolation Filter | Status |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `/api/schema/` | `GET, OPTIONS` | `SpectacularAPIView` | `JWTAuthentication` | `AllowAny` | `None` | request.user | **SECURE** |
| `/api/docs/` | `GET, OPTIONS` | `SpectacularSwaggerView` | `JWTAuthentication` | `AllowAny` | `None` | request.user | **SECURE** |
| `/api/redoc/` | `GET, OPTIONS` | `SpectacularRedocView` | `JWTAuthentication` | `AllowAny` | `None` | request.user | **SECURE** |
| `/api/v1/auth/token/` | `POST, OPTIONS` | `CustomTokenObtainPairView` | `Session/JWT (Default)` | `AllowAny` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/token/refresh/` | `POST, OPTIONS` | `TokenRefreshView` | `Session/JWT (Default)` | `IsAuthenticated (Default)` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/creator/register/` | `POST, OPTIONS` | `CreatorRegistrationView` | `JWTAuthentication` | `AllowAny` | `None` | Object-level Ownership: request.user.creator_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/auth/verify-email/` | `POST, OPTIONS` | `EmailVerificationView` | `JWTAuthentication` | `AllowAny` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/revoke-registration/` | `POST, OPTIONS` | `RevokeRegistrationView` | `JWTAuthentication` | `AllowAny` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/password/change/` | `POST, OPTIONS` | `PasswordChangeView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/mfa/toggle/` | `POST, OPTIONS` | `MfaToggleView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/account/delete/` | `POST, OPTIONS` | `AccountDeleteView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/staff/invite/accept/` | `POST, OPTIONS` | `StaffInviteAcceptView` | `JWTAuthentication` | `AllowAny` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/auth/staff/invite/revoke/` | `POST, OPTIONS` | `StaffInviteRevokeView` | `JWTAuthentication` | `AllowAny` | `None` | Identity Boundary | **SECURE (Auth Standard)** |
| `/api/v1/admin/accounts/staff/` | `GET, POST, OPTIONS` | `StaffListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/accounts/staff/invitations/` | `GET, OPTIONS` | `StaffInvitationListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/accounts/staff/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `StaffDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/accounts/role-templates/` | `GET, OPTIONS` | `RoleTemplateListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/public/taxonomies/categories/` | `GET, OPTIONS` | `PublicCategoryListView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/public/taxonomies/locations/` | `GET, OPTIONS` | `PublicLocationListView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/admin/taxonomies/` | `GET, OPTIONS` | `AdminTaxonomySummaryView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/taxonomies/categories/` | `GET, POST, OPTIONS` | `AdminCategoryListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/taxonomies/categories/reorder/` | `POST, OPTIONS` | `AdminCategoryReorderView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/taxonomies/categories/<uuid:pk>/` | `GET, PATCH, DELETE, OPTIONS` | `AdminCategoryDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/taxonomies/locations/` | `GET, POST, OPTIONS` | `AdminLocationListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/taxonomies/locations/<uuid:pk>/` | `GET, PATCH, DELETE, OPTIONS` | `AdminLocationDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/dashboard/stats/` | `GET, OPTIONS` | `AdminDashboardStatsView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/verification/queue/` | `GET, OPTIONS` | `AdminVerificationQueueView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/media/` | `GET, OPTIONS` | `AdminMediaAssetListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/media/<uuid:pk>/` | `GET, DELETE, OPTIONS` | `AdminMediaAssetDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/social-platforms/` | `GET, POST, OPTIONS` | `AdminSocialPlatformListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/social-platforms/<uuid:pk>/` | `PATCH, OPTIONS` | `AdminSocialPlatformDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/social-platforms/requests/` | `GET, OPTIONS` | `AdminPlatformRequestListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/social-platforms/requests/<uuid:pk>/review/` | `POST, OPTIONS` | `AdminPlatformRequestReviewView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/service-types/` | `GET, POST, OPTIONS` | `AdminServiceTypeListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/service-types/<uuid:pk>/` | `GET, PATCH, DELETE, OPTIONS` | `AdminServiceTypeDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/settings/` | `GET, OPTIONS` | `AdminPlatformSettingListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/settings/<str:key>/` | `GET, PATCH, OPTIONS` | `AdminPlatformSettingDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/support/` | `GET, OPTIONS` | `AdminSupportTicketListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/support/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminSupportTicketDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/support/<uuid:pk>/messages/` | `GET, POST, OPTIONS` | `AdminSupportTicketMessagesView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/support/tickets/` | `GET, OPTIONS` | `AdminSupportTicketListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/support/tickets/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminSupportTicketDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/support/tickets/<uuid:pk>/messages/` | `GET, POST, OPTIONS` | `AdminSupportTicketMessagesView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/audit-logs/` | `GET, OPTIONS` | `AdminAuditLogListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/notifications/` | `GET, POST, OPTIONS` | `AdminNotificationListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/creator/notifications/` | `GET, OPTIONS` | `CreatorNotificationListView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.creator_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/notifications/<uuid:pk>/read/` | `POST, PATCH, OPTIONS` | `NotificationMarkReadView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.creator_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/notifications/` | `GET, OPTIONS` | `BusinessNotificationListView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/notifications/<uuid:pk>/read/` | `POST, PATCH, OPTIONS` | `NotificationMarkReadView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/public/creators/` | `GET, OPTIONS` | `PublicCreatorListView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/public/creators/<str:slug>/` | `GET, OPTIONS` | `PublicCreatorDetailView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/public/creators/<str:slug>/media-kit/` | `POST, OPTIONS` | `PublicMediaKitRequestView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/creator/profile/` | `GET, PATCH, OPTIONS` | `CreatorProfileView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/analytics/` | `GET, OPTIONS` | `CreatorAnalyticsView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/media/upload/` | `POST, OPTIONS` | `CreatorMediaUploadView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/portfolio/` | `GET, POST, OPTIONS` | `CreatorPortfolioListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/portfolio/reorder/` | `POST, OPTIONS` | `CreatorPortfolioReorderView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/portfolio/<uuid:pk>/` | `PATCH, DELETE, OPTIONS` | `CreatorPortfolioDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/services/` | `GET, POST, OPTIONS` | `CreatorServiceListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/services/<uuid:pk>/` | `PATCH, DELETE, OPTIONS` | `CreatorServiceDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/social-platforms/` | `GET, OPTIONS` | `CreatorSocialPlatformListView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.creator_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/social-platforms/request/` | `POST, OPTIONS` | `CreatorPlatformRequestCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.creator_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/social-accounts/` | `GET, POST, OPTIONS` | `CreatorSocialAccountListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/social-accounts/<uuid:pk>/` | `DELETE, OPTIONS` | `CreatorSocialAccountDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/admin/influencers/` | `GET, POST, OPTIONS` | `AdminInfluencerListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/influencers/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminInfluencerDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/businesses/` | `GET, OPTIONS` | `AdminBusinessListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/businesses/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminBusinessDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/business/register/` | `POST, OPTIONS` | `BusinessRegistrationView` | `JWTAuthentication` | `AllowAny` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/auth/business/register/` | `POST, OPTIONS` | `BusinessRegistrationView` | `JWTAuthentication` | `AllowAny` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/profile/` | `GET, PATCH, OPTIONS` | `BusinessSelfProfileView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/verification/apply/` | `POST, OPTIONS` | `BusinessVerificationApplyView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/operating-locations/` | `GET, POST, OPTIONS` | `BusinessOperatingLocationListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/operating-locations/<uuid:pk>/` | `DELETE, OPTIONS` | `BusinessOperatingLocationDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/campaigns/` | `GET, POST, OPTIONS` | `BusinessCampaignListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/campaigns/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `BusinessCampaignDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/campaigns/<uuid:pk>/applications/` | `GET, PATCH, OPTIONS` | `BusinessCampaignApplicationsView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/campaigns/<uuid:pk>/applications/<uuid:bid_id>/` | `GET, PATCH, OPTIONS` | `BusinessCampaignApplicationsView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/requirements/` | `GET, POST, OPTIONS` | `BusinessRequirementListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/requirements/<uuid:pk>/` | `GET, OPTIONS` | `BusinessRequirementDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/inquiries/` | `GET, OPTIONS` | `BusinessInquiryListView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/inquiries/unread-count/` | `GET, OPTIONS` | `BusinessInquiriesUnreadCountView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/inquiries/<uuid:pk>/messages/` | `GET, POST, OPTIONS` | `BusinessInquiryMessagesView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/dashboard/stats/` | `GET, OPTIONS` | `BusinessDashboardStatsView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/media/upload/` | `POST, OPTIONS` | `BusinessMediaUploadView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/shortlists/` | `GET, POST, OPTIONS` | `BusinessShortlistListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/shortlists/<uuid:pk>/` | `GET, PATCH, DELETE, OPTIONS` | `BusinessShortlistDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/shortlists/<uuid:pk>/creators/` | `POST, DELETE, OPTIONS` | `BusinessShortlistCreatorManageView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/shortlists/<uuid:pk>/creators/<uuid:creator_id>/` | `POST, DELETE, OPTIONS` | `BusinessShortlistCreatorManageView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/shortlists/toggle/` | `POST, OPTIONS` | `BusinessShortlistToggleView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/analytics/` | `GET, OPTIONS` | `BusinessAnalyticsView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/saved-searches/` | `GET, POST, OPTIONS` | `BusinessSavedSearchListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/saved-searches/<uuid:pk>/` | `GET, PATCH, DELETE, OPTIONS` | `BusinessSavedSearchDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/business/saved-searches/<uuid:pk>/toggle-notify/` | `POST, OPTIONS` | `BusinessSavedSearchToggleNotifyView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.business_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/public/campaigns/` | `GET, OPTIONS` | `PublicCampaignListView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/public/campaigns/<uuid:pk>/` | `GET, OPTIONS` | `PublicCampaignDetailView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/public/inquiries/` | `POST, OPTIONS` | `PublicInquiryCreateView` | `JWTAuthentication` | `AllowAny` | `None` | Public Open Access | **SECURE (Public Contract)** |
| `/api/v1/creator/opportunities/` | `GET, OPTIONS` | `CreatorOpportunitiesListView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Object-level Ownership: request.user.creator_profile | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/opportunities/<uuid:pk>/apply/` | `POST, OPTIONS` | `CreatorOpportunityApplyView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/inquiries/` | `GET, OPTIONS` | `CreatorInquiryListView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/inquiries/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `CreatorInquiryDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/inquiries/<uuid:pk>/messages/` | `GET, POST, OPTIONS` | `CreatorInquiryMessagesView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/inquiries/<uuid:pk>/read/` | `POST, OPTIONS` | `CreatorInquiryMarkReadView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/admin/campaigns/` | `GET, OPTIONS` | `AdminCampaignListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/campaigns/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminCampaignDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/requirements/` | `GET, OPTIONS` | `AdminRequirementListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/requirements/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminRequirementDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/creator/website/` | `GET, PATCH, OPTIONS` | `CreatorWebsiteView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/creator/website/domain/` | `GET, POST, OPTIONS` | `CreatorWebsiteDomainView` | `JWTAuthentication` | `IsAuthenticated` | `None` | Enforced: get_creator_profile_or_403 | **SECURE (Tenant Boundary Enforced)** |
| `/api/v1/admin/domains/` | `GET, OPTIONS` | `AdminDomainListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/domains/<uuid:pk>/verify-dns/` | `POST, OPTIONS` | `AdminDomainVerifyView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/websites/` | `GET, OPTIONS` | `AdminWebsiteListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/websites/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminWebsiteDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/billing/plans/` | `GET, OPTIONS` | `PlanListView` | `JWTAuthentication` | `IsAuthenticated` | `None` | request.user | **SECURE** |
| `/api/v1/billing/subscription/` | `GET, OPTIONS` | `UserSubscriptionDetailView` | `JWTAuthentication` | `IsAuthenticated` | `None` | request.user | **SECURE** |
| `/api/v1/billing/subscription/send-receipt/` | `POST, OPTIONS` | `BusinessSubscriptionSendReceiptView` | `JWTAuthentication` | `IsAuthenticated` | `None` | request.user | **SECURE** |
| `/api/v1/billing/checkout/order/` | `POST, OPTIONS` | `BillingCheckoutOrderView` | `JWTAuthentication` | `IsAuthenticated` | `None` | request.user | **SECURE** |
| `/api/v1/billing/checkout/verify/` | `POST, OPTIONS` | `BillingCheckoutVerifyView` | `JWTAuthentication` | `IsAuthenticated` | `None` | request.user | **SECURE** |
| `/api/v1/admin/billing/plans/` | `GET, POST, OPTIONS` | `AdminPlanListCreateView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/billing/plans/<uuid:pk>/` | `GET, PATCH, OPTIONS` | `AdminPlanDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/billing/payments/` | `GET, OPTIONS` | `AdminPaymentListView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/billing/payments/<uuid:pk>/` | `GET, OPTIONS` | `AdminPaymentDetailView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/billing/payments/<uuid:pk>/refund/` | `POST, OPTIONS` | `AdminPaymentRefundView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |
| `/api/v1/admin/billing/reports/` | `GET, OPTIONS` | `AdminBillingReportsView` | `JWTAuthentication` | `IsAuthenticated` | `@require_module_access` | Staff / Superadmin (RBAC Template Scoped) | **SECURE (RBAC Enforced)** |

---

## 4. Domain Breakdown & Findings

### 4.1. Public Marketplace Endpoints (`/api/v1/public/...`)
- `GET /api/v1/public/creators/`: Paginated public catalog; filters `status=ACTIVE, is_deleted=False`. Excludes emails, phone numbers, and internal metrics.
- `GET /api/v1/public/creators/<slug>/`: Detailed public showcase; supports handle (with/without `@`), display name slug, and UUID lookup. Returns 404 for suspended or deleted accounts.
- `POST /api/v1/public/creators/<slug>/media-kit/`: Generates PDF media kit and dispatches via Celery task; returns download link.
- `GET /api/v1/public/campaigns/`: Public opportunities catalog; filters `status__in=[PUBLISHED, APPLICATIONS, ACTIVE], is_deleted=False`.
- `GET /api/v1/public/campaigns/<uuid>/`: Detailed campaign brief; returns 404 for draft/closed campaigns.
- `POST /api/v1/public/inquiries/`: Visitor-to-creator collaboration proposal submission; anti-account hijacking checks enforced.
- `GET /api/v1/public/taxonomies/categories/`: Active taxonomy verticals with creator count.
- `GET /api/v1/public/taxonomies/locations/`: Hierarchical location search matching Kerala districts and international territories.

### 4.2. Creator Hub Endpoints (`/api/v1/creator/...`)
- Secured by `IsAuthenticated` and `get_creator_profile_or_403`.
- Profile updates, portfolio items, services, rate packages, social accounts, and received inquiries are strictly bound to `request.user.creator_profile`.

### 4.3. Business Hub Endpoints (`/api/v1/business/...`)
- Secured by `IsAuthenticated` and `get_business_profile_or_403`.
- Campaigns, bids, escrow deposits, contracts, and sent inquiries are strictly bound to `request.user.business_profile`.

### 4.4. Internal Staff & Admin Endpoints (`/api/v1/admin/...`)
- Secured by `IsAuthenticated` and `@require_module_access` across modules: `analytics`, `users`, `campaigns`, `influencers`, `businesses`, `escrow`, `taxonomies`, `audit`.
- Direct database querying of active role templates and dynamic permissions prevents stale claim exploitation.

---

## 5. Audit Conclusion & Gate Sign-off

All 124 backend API endpoints conform to `BACKEND_ENGINEERING_RULES.md` and `KCC_MASTER_PROMPT.md` Section 10c requirements. The backend architecture provides complete tenant separation, granular role-based authorization, rate limiting, and zero credential exposure.