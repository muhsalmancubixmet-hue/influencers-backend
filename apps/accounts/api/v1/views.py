from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import (
    StaffProfile,
    RoleTemplate,
    StaffInvitation,
    ModuleChoice
)
from apps.accounts.decorators import require_module_access
from apps.accounts.api.v1.serializers import (
    CustomTokenObtainPairSerializer,
    StaffProfileSerializer,
    StaffInviteSerializer,
    StaffInvitationSerializer,
    StaffInviteAcceptSerializer,
    StaffInviteRevokeSerializer,
    RoleTemplateSerializer,
    CreatorRegistrationSerializer,
    EmailVerificationSerializer,
    RevokeRegistrationSerializer,
    PasswordChangeSerializer,
    AccountDeleteSerializer
)
from apps.accounts.api.v1.services import (
    invite_staff_member,
    accept_staff_invitation,
    revoke_staff_invitation,
    update_staff_profile,
    register_creator,
    verify_creator_email,
    revoke_creator_registration
)
from apps.common.api.v1.services import record_audit_log



class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Authenticate user credentials and issue SimpleJWT pair populated with
    tenancy role, staff privilege flag, and polymorphic profile identity.
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'


class RoleTemplateListView(APIView):
    """
    Control panel view returning standard role templates and their 14-module clearance matrix.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        List all active role templates with permissions.
        
        :param request: Authenticated HTTP request.
        :return: JSON array of role templates and module clearances.
        """
        templates = RoleTemplate.objects.filter(is_deleted=False).prefetch_related(
            'permissions',
            'assigned_staff'
        )
        serializer = RoleTemplateSerializer(templates, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StaffListCreateView(APIView):
    """
    List active staff members with pagination, and invite new staff members.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        List all staff accounts with their assigned role template.
        
        :param request: Authenticated HTTP request.
        :return: Paginated list of staff members.
        """
        profiles = StaffProfile.objects.select_related('user', 'role_template').filter(
            is_deleted=False
        ).order_by('-created_at')

        # Simple search filtering
        search = request.query_params.get('search', '').strip()
        if search:
            profiles = profiles.filter(
                user__email__icontains=search
            ) | profiles.filter(
                user__first_name__icontains=search
            ) | profiles.filter(
                user__last_name__icontains=search
            )

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(profiles, request)
        serializer = StaffProfileSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @require_module_access(ModuleChoice.SETTINGS, 'MANAGE')
    def post(self, request, *args, **kwargs):
        """
        Send an administrative invitation to a new staff member.
        
        :param request: Authenticated HTTP request containing email and role_template_id.
        :return: Created invitation details.
        """
        serializer = StaffInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            invitation = invite_staff_member(
                email=serializer.validated_data['email'],
                role_template_id=str(serializer.validated_data['role_template_id']),
                invited_by=request.user,
                first_name=serializer.validated_data.get('first_name', ''),
                last_name=serializer.validated_data.get('last_name', '')
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = StaffInvitationSerializer(invitation)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class StaffInvitationListView(APIView):
    """
    List pending, active, and expired administrative staff invitations.
    Restricted to administrators with SETTINGS VIEW clearance.
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, *args, **kwargs):
        """
        Retrieve all unaccepted staff invitations.

        :param request: Authenticated HTTP request.
        :return: JSON array of pending staff invitations.
        """
        invitations = StaffInvitation.objects.select_related('role_template', 'invited_by').filter(
            is_deleted=False
        ).order_by('-created_at')

        serializer = StaffInvitationSerializer(invitations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StaffInviteAcceptView(APIView):
    """
    Public administrative onboarding endpoint for invited staff members.
    Validates token, sets account password, and issues SimpleJWT access tokens.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        """
        Redeem invitation token and activate administrative account.

        :param request: Public HTTP request containing token and password payload.
        :return: JSON response with user details and authentication credentials.
        """
        serializer = StaffInviteAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = accept_staff_invitation(
                token=str(serializer.validated_data['token']),
                password=serializer.validated_data['password'],
                first_name=serializer.validated_data.get('first_name', ''),
                last_name=serializer.validated_data.get('last_name', '')
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        user = result['user']
        staff_profile = result['staff_profile']
        role_name = staff_profile.role_template.name if staff_profile.role_template else "Admin"

        return Response({
            'detail': 'Invitation accepted successfully. Your account is now active.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'role_name': role_name,
                'is_staff': True,
                'profile_id': str(staff_profile.id),
            },
            'tokens': result['tokens']
        }, status=status.HTTP_200_OK)


class StaffInviteRevokeView(APIView):
    """
    Public administrative invitation revocation endpoint.
    Allows an invited prospective staff member or administrator to decline/revoke an invitation.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        """
        Revoke pending staff invitation using token.

        :param request: Public HTTP request containing revocation token.
        :return: JSON confirmation of invitation cancellation.
        """
        serializer = StaffInviteRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = revoke_staff_invitation(
                token=str(serializer.validated_data['token'])
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class StaffDetailView(APIView):
    """
    Retrieve or update an individual staff profile (role reassignment, access toggle).
    """
    permission_classes = [IsAuthenticated]

    @require_module_access(ModuleChoice.SETTINGS, 'VIEW')
    def get(self, request, pk, *args, **kwargs):
        """
        Retrieve staff profile details.
        
        :param request: Authenticated HTTP request.
        :param pk: StaffProfile UUID.
        :return: StaffProfile details.
        """
        try:
            profile = StaffProfile.objects.select_related('user', 'role_template').get(
                id=pk,
                is_deleted=False
            )
        except (StaffProfile.DoesNotExist, ValueError):
            return Response({'detail': 'Staff member not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StaffProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @require_module_access(ModuleChoice.SETTINGS, 'MANAGE')
    def patch(self, request, pk, *args, **kwargs):
        """
        Update staff role template or access status.
        
        :param request: Authenticated HTTP request.
        :param pk: StaffProfile UUID.
        :return: Updated staff profile details.
        """
        role_template_id = request.data.get('role_template_id')
        is_active = request.data.get('is_active')

        try:
            profile = update_staff_profile(
                staff_profile_id=str(pk),
                role_template_id=str(role_template_id) if role_template_id else None,
                is_active=is_active if isinstance(is_active, bool) else None
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = StaffProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreatorRegistrationView(APIView):
    """
    Public creator onboarding endpoint.
    Accepts email, password, handle, display_name, creates inactive user and profile,
    and dispatches verification email asynchronously.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        """
        Process creator registration payload.

        :param request: Public HTTP request with creator registration credentials.
        :return: JSON response with created creator identity and status.
        """
        serializer = CreatorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = register_creator(
                email=serializer.validated_data['email'],
                username=serializer.validated_data['username'],
                password=serializer.validated_data.get('password')
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        user = result['user']
        profile = result['profile']

        return Response({
            'detail': 'Creator registered successfully. A magic login link has been dispatched to your email.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'profile_id': str(profile.id),
                'handle': profile.handle,
                'display_name': profile.display_name
            }
        }, status=status.HTTP_201_CREATED)


class EmailVerificationView(APIView):
    """
    Verify creator electronic mail token, activate account, and issue SimpleJWT credentials
    for immediate one-click authenticated dashboard access.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        """
        Validate verification token, activate creator account, and return JWT tokens.

        :param request: Public HTTP request containing verification token.
        :return: JSON confirmation with user activation status and JWT access/refresh tokens.
        """
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = verify_creator_email(
                token=serializer.validated_data['token'],
                email=serializer.validated_data.get('email')
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        user = result['user']
        profile = result.get('profile')

        return Response({
            'detail': 'Email verified successfully. Account is now active.',
            'access': result['access'],
            'refresh': result['refresh'],
            'user': {
                'id': str(user.id),
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'profile_id': str(profile.id) if profile else None,
                'handle': profile.handle if profile else '',
                'display_name': profile.display_name if profile else ''
            }
        }, status=status.HTTP_200_OK)


class RevokeRegistrationView(APIView):
    """
    Instantly revoke an unconfirmed or unintended creator registration.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        """
        Validate revocation token and cancel creator registration.

        :param request: Public HTTP request containing revocation token.
        :return: JSON confirmation of account revocation.
        """
        serializer = RevokeRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = revoke_creator_registration(
                token=serializer.validated_data['token']
            )
        except ValidationError as err:
            return Response({'detail': err.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class PasswordChangeView(APIView):
    """
    Authenticated credential change endpoint.
    
    Verifies user's active current password before applying new credentials.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request, *args, **kwargs):
        """
        Change authenticated user password.
        
        :param request: Authenticated HTTP request containing current and new password.
        :return: JSON success confirmation.
        """
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        new_password = serializer.validated_data['new_password']
        user.set_password(new_password)
        user.save()

        record_audit_log(
            admin=user,
            action='CHANGE_PASSWORD',
            entity='User',
            entity_id=str(user.id),
            result='SUCCESS',
            reason="User successfully updated login password."
        )

        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)


class MfaToggleView(APIView):
    """
    Two-step verification status toggle endpoint.
    
    Enables or disables multi-factor authentication for the authenticated account.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Toggle MFA status.
        
        :param request: Authenticated HTTP request.
        :return: JSON response with new mfa_enabled boolean flag.
        """
        user = request.user
        explicit_val = request.data.get('mfa_enabled')
        if explicit_val is not None:
            user.mfa_enabled = bool(explicit_val)
        else:
            user.mfa_enabled = not user.mfa_enabled
        user.save(update_fields=['mfa_enabled', 'updated_at'])

        record_audit_log(
            admin=user,
            action='TOGGLE_MFA',
            entity='User',
            entity_id=str(user.id),
            result='SUCCESS',
            reason=f"MFA toggled to {user.mfa_enabled}"
        )

        return Response({
            'mfa_enabled': user.mfa_enabled,
            'detail': f"Two-step verification {'enabled' if user.mfa_enabled else 'disabled'} successfully."
        }, status=status.HTTP_200_OK)


class AccountDeleteView(APIView):
    """
    Permanent account deletion endpoint (Danger Zone).
    
    Requires password confirmation, marks records soft-deleted, and deactivates access.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Execute account deletion after password verification.
        
        :param request: Authenticated HTTP request containing confirmation password.
        :return: JSON confirmation of account deletion.
        """
        serializer = AccountDeleteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        profile = getattr(user, 'creator_profile', None)

        if profile:
            profile.soft_delete()

        user.is_active = False
        user.soft_delete()

        record_audit_log(
            admin=user,
            action='DELETE_ACCOUNT',
            entity='User',
            entity_id=str(user.id),
            result='SUCCESS',
            reason="Account permanently scheduled for deletion by user."
        )

        return Response({'detail': 'Account permanently deleted and deactivated.'}, status=status.HTTP_200_OK)


