from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import (
    User,
    StaffProfile,
    RoleTemplate,
    RolePermission,
    StaffInvitation,
    UserRole
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Enhanced JWT token serializer embedding tenancy role, staff privileges,
    and polymorphic profile ID within access token claims and login response.
    """

    @classmethod
    def get_token(cls, user: User):
        """
        Populate custom token claims for immediate client-side tenant routing.
        
        :param user: Authenticated User entity.
        :return: Token payload with role, is_staff, and profile_id claims.
        """
        token = super().get_token(user)

        # Custom claims
        token['email'] = user.email
        token['role'] = user.role
        token['is_staff'] = (
            user.role in [UserRole.STAFF, UserRole.SUPER_ADMIN]
            or user.is_staff
            or user.is_superuser
        )

        # Polymorphic profile identifier lookup
        profile_id = None
        if user.role == UserRole.CREATOR and hasattr(user, 'creator_profile'):
            profile_id = str(user.creator_profile.id)
        elif user.role == UserRole.BUSINESS and hasattr(user, 'business_profile'):
            profile_id = str(user.business_profile.id)
        elif hasattr(user, 'staff_profile'):
            profile_id = str(user.staff_profile.id)

        token['profile_id'] = profile_id
        return token

    def validate(self, attrs):
        """
        Validate credentials, enforce tenant boundary access rules, and return token pair.
        
        Evaluates whether the authenticating user is authorized to access the requested portal
        (e.g., admin control panel vs creator workspace). Rejects cross-tenant logins immediately.
        
        :param attrs: Authentication payload (username/email and password).
        :return: Dictionary containing access token, refresh token, and user payload.
        :raises serializers.ValidationError: When credentials are invalid or user violates portal tenant boundary.
        """
        data = super().validate(attrs)

        # -------------------------------------------------------------
        # STEP 1: Determine target portal from request headers or body
        # -------------------------------------------------------------
        request = self.context.get('request')
        target_portal = None
        if request is not None:
            target_portal = (
                request.headers.get('X-Target-Portal')
                or request.META.get('HTTP_X_TARGET_PORTAL')
            )
        if not target_portal and hasattr(self, 'initial_data') and isinstance(self.initial_data, dict):
            target_portal = self.initial_data.get('portal')

        # -------------------------------------------------------------
        # STEP 2: Strict Tenant Boundary Enforcement (Rule 3)
        # -------------------------------------------------------------
        is_staff_user = (
            self.user.role in [UserRole.STAFF, UserRole.SUPER_ADMIN]
            or self.user.is_staff
            or self.user.is_superuser
        )

        if target_portal:
            normalized_portal = str(target_portal).strip().lower()
            if normalized_portal == 'admin' and not is_staff_user:
                raise serializers.ValidationError({
                    "detail": "Access forbidden: This administration control panel is strictly restricted to internal staff and super administrators. Influencer and creator accounts must sign in via the Creator Hub."
                })
            elif normalized_portal == 'creator' and self.user.role != UserRole.CREATOR and not self.user.is_superuser:
                raise serializers.ValidationError({
                    "detail": "Access forbidden: This portal is strictly restricted to creator accounts."
                })

        # -------------------------------------------------------------
        # STEP 3: Polymorphic profile identifier resolution
        # -------------------------------------------------------------
        profile_id = None
        if self.user.role == UserRole.CREATOR and hasattr(self.user, 'creator_profile'):
            profile_id = str(self.user.creator_profile.id)
        elif self.user.role == UserRole.BUSINESS and hasattr(self.user, 'business_profile'):
            profile_id = str(self.user.business_profile.id)
        elif hasattr(self.user, 'staff_profile'):
            profile_id = str(self.user.staff_profile.id)

        data['user'] = {
            'id': str(self.user.id),
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': self.user.role,
            'is_staff': is_staff_user,
            'profile_id': profile_id
        }
        return data


class RolePermissionSerializer(serializers.ModelSerializer):
    """Serializer representing granular module clearance tier in role template."""

    class Meta:
        model = RolePermission
        fields = ['id', 'module', 'access_level', 'weight']
        read_only_fields = ['id', 'weight']


class RoleTemplateSerializer(serializers.ModelSerializer):
    """Serializer representing a standard staff role template with clearance matrix."""
    permissions = RolePermissionSerializer(many=True, read_only=True)
    assigned_count = serializers.IntegerField(source='assigned_staff.count', read_only=True)

    class Meta:
        model = RoleTemplate
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'is_system',
            'assigned_count',
            'permissions',
            'created_at'
        ]
        read_only_fields = ['id', 'is_system', 'assigned_count', 'permissions', 'created_at']


class StaffUserSerializer(serializers.ModelSerializer):
    """Compact serializer for user account fields bound to staff profiles."""

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'is_active', 'last_login']
        read_only_fields = ['id', 'last_login']


class StaffProfileSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for staff profiles with role template details."""
    user = StaffUserSerializer(read_only=True)
    role_template = RoleTemplateSerializer(read_only=True)
    role_template_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = StaffProfile
        fields = [
            'id',
            'user',
            'role_template',
            'role_template_id',
            'is_active',
            'last_active_at',
            'created_at'
        ]
        read_only_fields = ['id', 'user', 'role_template', 'last_active_at', 'created_at']


class StaffInviteSerializer(serializers.Serializer):
    """Payload contract for dispatching staff onboarding invitations."""
    email = serializers.EmailField()
    role_template_id = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_role_template_id(self, value: str) -> str:
        """Resolve role template by UUID or case-insensitive name."""
        from apps.accounts.models import RoleTemplate
        import uuid

        clean_val = str(value).strip()
        role = None
        try:
            val_uuid = uuid.UUID(clean_val)
            role = RoleTemplate.objects.filter(id=val_uuid, is_deleted=False).first()
        except ValueError:
            pass

        if not role:
            role = RoleTemplate.objects.filter(name__iexact=clean_val, is_deleted=False).first()

        if not role:
            raise serializers.ValidationError(f"Role template '{value}' does not exist.")

        return str(role.id)


class StaffInvitationSerializer(serializers.ModelSerializer):
    """Serializer representing pending staff invitations."""
    role_name = serializers.CharField(source='role_template.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = StaffInvitation
        fields = [
            'id',
            'email',
            'role_template',
            'role_name',
            'token',
            'expires_at',
            'is_accepted',
            'is_expired',
            'created_at'
        ]
        read_only_fields = ['id', 'token', 'is_accepted', 'is_expired', 'created_at']


class StaffInviteAcceptSerializer(serializers.Serializer):
    """
    Payload contract for redeeming an administrative staff invitation.
    Validates token and minimum password constraints.
    """
    token = serializers.UUIDField(help_text="Invitation token received via email.")
    password = serializers.CharField(min_length=8, write_only=True, help_text="Desired account password.")
    first_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=50, required=False, allow_blank=True)


class StaffInviteRevokeSerializer(serializers.Serializer):
    """Payload contract for revoking or declining an administrative staff invitation."""
    token = serializers.UUIDField(help_text="Unguessable invitation UUID token.")


class CreatorRegistrationSerializer(serializers.Serializer):
    """
    Input serializer for creator public registration.
    Only requires email and username (handle) for onboarding.
    Password and display name are automatically initialized if not provided.
    """
    email = serializers.EmailField(
        required=True,
        help_text="Primary electronic mail address for account and sign-in."
    )
    username = serializers.CharField(
        required=False,
        max_length=80,
        help_text="Unique creator username / handle (e.g. 'mayasharma')."
    )
    handle = serializers.CharField(
        required=False,
        max_length=80,
        help_text="Alternate field alias for username."
    )
    password = serializers.CharField(
        required=False,
        write_only=True,
        min_length=8,
        allow_blank=True,
        help_text="Optional custom password. If omitted, a secure password is generated automatically."
    )
    display_name = serializers.CharField(
        required=False,
        max_length=150,
        allow_blank=True,
        help_text="Optional custom display name. If omitted, initialized from username."
    )

    def validate(self, attrs: dict) -> dict:
        """Ensure either username or handle is provided and URL-safe."""
        raw_username = attrs.get('username') or attrs.get('handle')
        if not raw_username:
            raise serializers.ValidationError({"username": "Username is required."})

        clean = raw_username.strip().lstrip('@').lower()
        if not clean:
            raise serializers.ValidationError({"username": "Username cannot be empty."})
        if any(c in clean for c in " /\\?#%&"):
            raise serializers.ValidationError({"username": "Username must be URL-safe without spaces or special characters."})

        attrs['username'] = clean
        attrs['handle'] = clean
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """
    Input serializer for email token verification.
    """
    token = serializers.CharField(
        required=True,
        help_text="Verification token received via magic link email."
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        help_text="Optional creator email for fallback token matching."
    )


class RevokeRegistrationSerializer(serializers.Serializer):
    """
    Input serializer for instantaneous account registration revocation.
    """
    token = serializers.CharField(
        required=True,
        help_text="Revocation token received via email revocation button."
    )


class PasswordChangeSerializer(serializers.Serializer):
    """
    Payload contract for authenticated credential changes.
    Validates current password before setting new password.
    """
    current_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current login password for identity verification."
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="New strong password (min 8 characters)."
    )

    def validate_current_password(self, value: str) -> str:
        """
        Verify current password against authenticated user.
        
        :param value: Submitted current password string.
        :return: Validated current password string.
        :raises serializers.ValidationError: If current password does not match.
        """
        request = self.context.get('request')
        if not request or not request.user or not request.user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs: dict) -> dict:
        """
        Ensure new password differs from current password.
        
        :param attrs: Validated serializer fields.
        :return: Sanitized attributes dictionary.
        :raises serializers.ValidationError: If new password matches current password.
        """
        if attrs.get('current_password') == attrs.get('new_password'):
            raise serializers.ValidationError({"new_password": "New password cannot be identical to current password."})
        return attrs


class AccountDeleteSerializer(serializers.Serializer):
    """
    Payload contract for confirming account deletion in danger zone.
    Requires password verification to prevent accidental purge.
    """
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="User password required to authorize permanent account deletion."
    )

    def validate_password(self, value: str) -> str:
        """
        Verify password before authorizing deletion.
        
        :param value: Submitted confirmation password.
        :return: Validated password.
        :raises serializers.ValidationError: If password verification fails.
        """
        request = self.context.get('request')
        if not request or not request.user or not request.user.check_password(value):
            raise serializers.ValidationError("Password verification failed. Incorrect password.")
        return value


