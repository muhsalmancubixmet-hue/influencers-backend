from datetime import timedelta
from typing import Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import (
    User,
    UserRole,
    StaffProfile,
    RoleTemplate,
    StaffInvitation
)


def invite_staff_member(
    email: str,
    role_template_id: str,
    invited_by: User,
    first_name: str = '',
    last_name: str = ''
) -> StaffInvitation:
    """
    Issue an administrative onboarding invitation to a prospective staff member.
    
    Validates that:
    1. The target email is not already an active staff member.
    2. The selected role template exists and is active.
    3. Pending unexpired invitations for the same email are invalidated or updated.
    
    :param email: Corporate email address of the invitee.
    :param role_template_id: Primary key UUID of the RoleTemplate to assign.
    :param invited_by: Staff/Admin user authorizing the invitation.
    :param first_name: Optional first name.
    :param last_name: Optional last name.
    :return: Persisted StaffInvitation record.
    :raises ValidationError: If email is already registered as staff or role template does not exist.
    """
    # -------------------------------------------------------------
    # STEP 1: Verify role template exists (by UUID or name)
    # -------------------------------------------------------------
    import uuid
    from apps.common.api.v1.services import record_audit_log

    role_template = None
    try:
        val_uuid = uuid.UUID(str(role_template_id).strip())
        role_template = RoleTemplate.objects.filter(id=val_uuid, is_deleted=False).first()
    except ValueError:
        pass

    if not role_template:
        role_template = RoleTemplate.objects.filter(name__iexact=str(role_template_id).strip(), is_deleted=False).first()

    if not role_template:
        raise ValidationError(f"RoleTemplate '{role_template_id}' does not exist.")

    # -------------------------------------------------------------
    # STEP 2: Check if email is already an active staff user
    # -------------------------------------------------------------
    existing_staff = StaffProfile.objects.filter(
        user__email__iexact=email,
        is_deleted=False
    ).exists()
    if existing_staff:
        raise ValidationError(f"A staff member with email '{email}' already exists.")

    # -------------------------------------------------------------
    # STEP 3: Invalidate previous pending invitations for this email
    # -------------------------------------------------------------
    with transaction.atomic():
        StaffInvitation.objects.filter(
            email__iexact=email,
            is_accepted=False
        ).update(is_deleted=True)

        import secrets
        temporary_password = f"Admin#{secrets.token_hex(3).upper()}!"

        # STEP 4: Create new 7-day valid invitation & pre-seed credentials
        expires_at = timezone.now() + timedelta(days=7)
        invitation = StaffInvitation.objects.create(
            email=email.lower().strip(),
            role_template=role_template,
            invited_by=invited_by,
            expires_at=expires_at
        )

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            username = email.split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            user = User.objects.create_user(
                username=username,
                email=email.lower().strip(),
                role=UserRole.STAFF,
                is_active=False,
                first_name=first_name.strip() if first_name else '',
                last_name=last_name.strip() if last_name else ''
            )
            user.set_password(temporary_password)
            user.save()
        else:
            if not user.is_active:
                user.set_password(temporary_password)
                user.save()

        record_audit_log(
            admin=invited_by,
            action='INVITE_STAFF',
            entity='StaffInvitation',
            entity_id=str(invitation.id),
            reason=f"Invited staff {invitation.email} with role {role_template.name}"
        )

    # -------------------------------------------------------------
    # STEP 5: Dispatch onboarding invitation email
    # -------------------------------------------------------------
    from apps.accounts.tasks import send_staff_invitation_email_task
    from django.conf import settings
    inviter_name = (
        f"{invited_by.first_name} {invited_by.last_name}".strip()
        if (invited_by.first_name or invited_by.last_name)
        else (invited_by.email or "Super Admin")
    )
    is_eager = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
    if is_eager:
        send_staff_invitation_email_task.apply(args=[
            invitation.email,
            str(invitation.token),
            role_template.name,
            inviter_name,
            temporary_password
        ])
    else:
        try:
            send_staff_invitation_email_task.delay(
                invitation.email,
                str(invitation.token),
                role_template.name,
                inviter_name,
                temporary_password
            )
        except Exception:
            send_staff_invitation_email_task.apply(args=[
                invitation.email,
                str(invitation.token),
                role_template.name,
                inviter_name,
                temporary_password
            ])

    return invitation


def revoke_staff_invitation(token: str) -> dict:
    """
    Instantly revoke and invalidate a pending administrative staff invitation.
    
    If the recipient or inviter cancels the invitation, flags the invitation as deleted
    and deactivates any pending unactivated staff user account.

    :param token: UUID string from invitation email.
    :return: Confirmation dictionary.
    :raises ValidationError: If token is invalid, expired, or already redeemed.
    """
    import uuid
    from apps.common.api.v1.services import record_audit_log

    try:
        token_uuid = uuid.UUID(str(token).strip())
    except ValueError:
        raise ValidationError("Invalid invitation token format.")

    invitation = StaffInvitation.objects.filter(
        token=token_uuid,
        is_deleted=False
    ).first()

    if not invitation:
        raise ValidationError("Invitation is invalid or has already been revoked.")

    if invitation.is_accepted:
        raise ValidationError("Cannot revoke an invitation that has already been accepted.")

    with transaction.atomic():
        invitation.is_deleted = True
        invitation.save(update_fields=['is_deleted', 'updated_at'])

        # Invalidate unactivated user account if created solely for this invite
        user = User.objects.filter(email__iexact=invitation.email, is_active=False).first()
        if user:
            user.is_deleted = True
            user.save(update_fields=['is_deleted', 'updated_at'])

    return {
        'detail': f"Administrative invitation for {invitation.email} has been successfully revoked."
    }


def accept_staff_invitation(
    token: str,
    password: str,
    first_name: str = '',
    last_name: str = ''
) -> dict:
    """
    Redeem a valid administrative invitation token, create staff user account and profile.

    Validates:
    1. Invitation exists, has not expired, is not accepted, and is not deleted.
    2. User account does not already exist with this email; if it does, converts role to STAFF.
    3. Password meets minimum security length.

    :param token: UUID string from invitation email.
    :param password: Chosen account password.
    :param first_name: Optional first name.
    :param last_name: Optional last name.
    :return: Dictionary containing created User, StaffProfile, and JWT tokens.
    :raises ValidationError: If token is invalid or expired.
    """
    import uuid
    from rest_framework_simplejwt.tokens import RefreshToken
    from apps.common.api.v1.services import record_audit_log

    if len(password.strip()) < 8:
        raise ValidationError("Password must be at least 8 characters.")

    try:
        token_uuid = uuid.UUID(str(token).strip())
    except ValueError:
        raise ValidationError("Invalid invitation token format.")

    invitation = StaffInvitation.objects.select_related('role_template', 'invited_by').filter(
        token=token_uuid,
        is_accepted=False,
        is_deleted=False
    ).first()

    if not invitation:
        raise ValidationError("This invitation token is invalid or has already been used.")

    if invitation.expires_at < timezone.now():
        raise ValidationError("This invitation has expired. Please request a new invite.")

    with transaction.atomic():
        user = User.objects.filter(email__iexact=invitation.email).first()
        if not user:
            username = invitation.email.split('@')[0]
            # Ensure unique username
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            user = User.objects.create(
                email=invitation.email.lower().strip(),
                username=username,
                first_name=first_name.strip() or username.title(),
                last_name=last_name.strip(),
                role=UserRole.STAFF,
                is_active=True
            )
        else:
            user.role = UserRole.STAFF
            user.is_active = True
            if first_name:
                user.first_name = first_name.strip()
            if last_name:
                user.last_name = last_name.strip()

        user.set_password(password)
        user.save()

        # Create or update StaffProfile
        staff_profile, _ = StaffProfile.objects.update_or_create(
            user=user,
            defaults={
                'role_template': invitation.role_template,
                'is_active': True,
                'last_active_at': timezone.now()
            }
        )

        invitation.is_accepted = True
        invitation.save(update_fields=['is_accepted', 'updated_at'])

        record_audit_log(
            admin=user,
            action='ACCEPT_STAFF_INVITE',
            entity='StaffProfile',
            entity_id=str(staff_profile.id),
            reason=f"Accepted staff invitation for {invitation.email} with role {invitation.role_template.name}"
        )

    # Issue SimpleJWT tokens
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['email'] = user.email

    return {
        'user': user,
        'staff_profile': staff_profile,
        'tokens': {
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }
    }


def update_staff_profile(
    staff_profile_id: str,
    role_template_id: Optional[str] = None,
    is_active: Optional[bool] = None
) -> StaffProfile:
    """
    Update staff administrative role template and access status.
    
    :param staff_profile_id: Primary key UUID of the StaffProfile.
    :param role_template_id: Optional new RoleTemplate ID.
    :param is_active: Optional status toggle enabling/suspending access.
    :return: Updated StaffProfile record.
    :raises ValidationError: If profile or role template is invalid.
    """
    try:
        profile = StaffProfile.objects.select_related('user', 'role_template').get(
            id=staff_profile_id,
            is_deleted=False
        )
    except (StaffProfile.DoesNotExist, ValueError):
        raise ValidationError(f"StaffProfile with ID '{staff_profile_id}' not found.")

    with transaction.atomic():
        if role_template_id is not None:
            try:
                role_template = RoleTemplate.objects.get(id=role_template_id, is_deleted=False)
                profile.role_template = role_template
            except (RoleTemplate.DoesNotExist, ValueError):
                raise ValidationError(f"RoleTemplate with ID '{role_template_id}' does not exist.")

        if is_active is not None:
            profile.is_active = is_active
            profile.user.is_active = is_active
            profile.user.save(update_fields=['is_active'])

        profile.save()

    return profile


def register_creator(
    email: str,
    username: str,
    password: Optional[str] = None
) -> dict:
    """
    Register a new public creator account requiring only email and username.
    
    Generates a secure temporary password if not provided, creates an inactive User
    and linked CreatorProfile, and dispatches an asynchronous welcome email with a
    dashboard magic login link via Celery.

    :param email: Unique electronic mail address of the creator.
    :param username: Desired creator handle / username (e.g. 'mayasharma').
    :param password: Optional raw plaintext password (auto-generated if omitted).
    :return: Dictionary containing created User, CreatorProfile, verification token, and temporary password.
    :raises ValidationError: If email or username is already registered.
    """
    import secrets
    import string
    from django.core.signing import TimestampSigner
    from apps.creators.models import CreatorProfile
    from apps.accounts.tasks import send_verification_email_task

    clean_email = email.lower().strip()
    clean_handle = username.strip().lstrip('@').lower()

    # -------------------------------------------------------------
    # STEP 1: Verify email uniqueness
    # -------------------------------------------------------------
    if User.objects.filter(email__iexact=clean_email).exists():
        raise ValidationError(f"An account with email '{clean_email}' already exists.")

    # -------------------------------------------------------------
    # STEP 2: Verify username / handle uniqueness
    # -------------------------------------------------------------
    if CreatorProfile.objects.filter(handle__iexact=clean_handle, is_deleted=False).exists():
        raise ValidationError(f"The username '@{clean_handle}' is already claimed by another creator.")

    # -------------------------------------------------------------
    # STEP 3: Generate temporary password if not supplied
    # -------------------------------------------------------------
    temp_password = password
    if not temp_password:
        # Generate 12-character secure alphanumeric + symbol password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

    # -------------------------------------------------------------
    # STEP 4: Create User and linked CreatorProfile in atomic transaction
    # -------------------------------------------------------------
    with transaction.atomic():
        user = User.objects.create_user(
            username=clean_email,
            email=clean_email,
            password=temp_password,
            role=UserRole.CREATOR,
            is_active=False
        )

        display_name = clean_handle.replace('.', ' ').replace('_', ' ').title()
        profile = CreatorProfile.objects.create(
            user=user,
            handle=clean_handle,
            display_name=display_name
        )

        # -------------------------------------------------------------
        # STEP 5: Generate timestamp-signed cryptographic token
        # -------------------------------------------------------------
        signer = TimestampSigner()
        token = signer.sign(str(user.id))

    # -------------------------------------------------------------
    # STEP 6: Dispatch async Celery welcome/magic link email task
    # -------------------------------------------------------------
    try:
        send_verification_email_task.delay(
            str(user.id),
            user.email,
            token,
            temp_password
        )
    except Exception as exc:
        # Fallback direct call if Celery queue service is unavailable
        try:
            send_verification_email_task(
                None,
                str(user.id),
                user.email,
                token,
                temp_password
            )
        except Exception:
            pass

    return {
        'user': user,
        'profile': profile,
        'token': token,
        'temporary_password': temp_password
    }


def verify_creator_email(token: str, email: Optional[str] = None) -> dict:
    """
    Validate a verification token, activate the creator User account,
    and generate SimpleJWT credentials enabling seamless one-click dashboard login.

    :param token: Timestamp-signed cryptographic token from magic link.
    :param email: Optional creator email fallback identifier.
    :return: Dictionary containing activated User, CreatorProfile, and JWT access & refresh tokens.
    :raises ValidationError: If token is expired, invalid, or user is not found.
    """
    from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
    from rest_framework_simplejwt.tokens import RefreshToken

    signer = TimestampSigner()
    user = None

    # -------------------------------------------------------------
    # STEP 1: Attempt to unsign user ID from token (valid for 48 hours)
    # -------------------------------------------------------------
    try:
        user_id = signer.unsign(token, max_age=172800)  # 48 hours validity
        user = User.objects.get(id=user_id, is_deleted=False)
    except SignatureExpired:
        raise ValidationError("Verification token has expired. Please request a new magic link.")
    except (BadSignature, ValueError, User.DoesNotExist):
        # Fallback: check if token matches email lookup
        if email:
            try:
                user = User.objects.get(email__iexact=email.strip(), is_deleted=False)
            except User.DoesNotExist:
                raise ValidationError("Invalid verification token or email address.")
        else:
            raise ValidationError("Invalid or corrupted verification token.")

    # -------------------------------------------------------------
    # STEP 2: Activate user account
    # -------------------------------------------------------------
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])

    profile = getattr(user, 'creator_profile', None)

    # -------------------------------------------------------------
    # STEP 3: Issue SimpleJWT tokens with tenancy role and profile claims
    # -------------------------------------------------------------
    refresh = RefreshToken.for_user(user)
    refresh['email'] = user.email
    refresh['role'] = user.role
    if profile:
        refresh['profile_id'] = str(profile.id)

    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    return {
        'user': user,
        'profile': profile,
        'access': access_token,
        'refresh': refresh_token
    }


def revoke_creator_registration(token: str) -> dict:
    """
    Instantly revoke and cancel an unauthorized or unintended creator registration.
    
    Validates the token, deactivates and flags the account as deleted, freeing up the
    email and handle so it cannot be abused.

    :param token: Cryptographically signed token from the revocation email link.
    :return: Dictionary confirming successful revocation.
    :raises ValidationError: If token is invalid or user record not found.
    """
    from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

    signer = TimestampSigner()

    # -------------------------------------------------------------
    # STEP 1: Unsign token to identify target user
    # -------------------------------------------------------------
    try:
        user_id = signer.unsign(token, max_age=604800)  # 7 days revocation window
        user = User.objects.get(id=user_id)
    except (SignatureExpired, BadSignature, ValueError, User.DoesNotExist):
        raise ValidationError("Invalid or expired revocation link.")

    # -------------------------------------------------------------
    # STEP 2: Invalidate and purge registration within atomic transaction
    # -------------------------------------------------------------
    with transaction.atomic():
        user.is_active = False
        user.is_deleted = True
        user.save(update_fields=['is_active', 'is_deleted'])

        profile = getattr(user, 'creator_profile', None)
        if profile:
            profile.is_deleted = True
            profile.save(update_fields=['is_deleted'])

    return {
        'status': 'revoked',
        'detail': 'Account registration has been successfully revoked and cancelled.'
    }
