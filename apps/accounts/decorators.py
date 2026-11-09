from functools import wraps
from typing import Callable, Any
from rest_framework import exceptions
from rest_framework.request import Request


def require_module_access(module_name: str, min_level: str = 'VIEW') -> Callable:
    """
    Method decorator for Django REST Framework APIViews enforcing dynamic database RBAC validation.
    
    Verifies that the authenticated user possesses sufficient clearance for the target module.
    Clearance is queried fresh from the database on every request to ensure immediate revocation
    without relying on cached permissions or stale JWT claims.
    
    Access Evaluation Rules:
    1. Unauthenticated requests are rejected with NotAuthenticated (401).
    2. Users with `is_superuser=True` or `role == 'SUPER_ADMIN'` automatically bypass all clearance checks.
    3. Users with any role other than `STAFF` are rejected with PermissionDenied (403).
    4. Staff profiles are queried fresh from the database with their associated RoleTemplate and RolePermission.
    5. The integer ranking weight of the granted access tier is compared against `min_level`.
       If insufficient or if permission is absent (NONE), PermissionDenied (403) is raised.
    
    :param module_name: The operational module key being accessed (e.g. 'campaigns', 'influencers').
    :param min_level: The minimum clearance tier required ('VIEW', 'MODERATE', 'MANAGE', 'FULL').
    :return: Wrapped view function that enforces RBAC validation before execution.
    :raises rest_framework.exceptions.NotAuthenticated: When request user is anonymous.
    :raises rest_framework.exceptions.PermissionDenied: When clearance is missing or insufficient.
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(view_instance: Any, request: Request, *args: Any, **kwargs: Any) -> Any:
            # -------------------------------------------------------------
            # STEP 1: Verify user authentication status
            # -------------------------------------------------------------
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                raise exceptions.NotAuthenticated(
                    detail="Authentication credentials were not provided or are invalid."
                )

            # -------------------------------------------------------------
            # STEP 2: Super Admin bypass check (is_superuser or SUPER_ADMIN role)
            # -------------------------------------------------------------
            if getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'SUPER_ADMIN':
                return view_func(view_instance, request, *args, **kwargs)

            # -------------------------------------------------------------
            # STEP 3: Ensure user belongs to the internal STAFF tenant boundary
            # -------------------------------------------------------------
            if getattr(user, 'role', '') != 'STAFF':
                raise exceptions.PermissionDenied(
                    detail="Access forbidden: This endpoint is strictly restricted to internal staff members."
                )

            # -------------------------------------------------------------
            # STEP 4: Query active StaffProfile fresh from database
            # -------------------------------------------------------------
            from apps.accounts.models import StaffProfile, RolePermission, ACCESS_TIER_WEIGHTS, AccessLevel
            
            staff_profile = StaffProfile.objects.select_related('role_template').filter(
                user=user,
                is_active=True,
                is_deleted=False
            ).first()

            if not staff_profile or not staff_profile.role_template:
                raise exceptions.PermissionDenied(
                    detail="Access forbidden: No active staff profile or role template is assigned to this account."
                )

            # -------------------------------------------------------------
            # STEP 5: Query granular RolePermission for the target module
            # -------------------------------------------------------------
            permission = RolePermission.objects.filter(
                role_template=staff_profile.role_template,
                module=module_name,
                is_deleted=False
            ).first()

            granted_level = permission.access_level if permission else AccessLevel.NONE
            granted_weight = ACCESS_TIER_WEIGHTS.get(granted_level, 0)

            # -------------------------------------------------------------
            # STEP 6: Resolve required clearance weight and compare
            # -------------------------------------------------------------
            # Map string to AccessLevel or resolve weight
            try:
                required_enum = AccessLevel[min_level.upper()]
                required_weight = ACCESS_TIER_WEIGHTS.get(required_enum, 99)
            except KeyError:
                required_weight = 99  # Safe fallback: deny if invalid min_level provided

            if granted_weight < required_weight:
                raise exceptions.PermissionDenied(
                    detail=(
                        f"Access forbidden: Insufficient clearance for module '{module_name}'. "
                        f"Required tier: '{min_level.upper()}', Assigned tier: '{granted_level}'."
                    )
                )

            # -------------------------------------------------------------
            # STEP 7: Permission verified - execute protected view method
            # -------------------------------------------------------------
            return view_func(view_instance, request, *args, **kwargs)

        return _wrapped_view
    return decorator
