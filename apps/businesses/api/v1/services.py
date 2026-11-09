from typing import Optional
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.businesses.models import BusinessProfile
from apps.common.api.v1.services import record_audit_log


def moderate_business(
    business_id: str,
    status: Optional[str] = None,
    verification_status: Optional[str] = None,
    admin_user: Optional[User] = None
) -> BusinessProfile:
    """
    Moderate business profile operational status and verification with compliance audit.
    
    :param business_id: UUID of BusinessProfile.
    :param status: Optional new BusinessStatus.
    :param verification_status: Optional new BusinessVerificationStatus.
    :param admin_user: Staff User performing moderation.
    :return: Updated BusinessProfile.
    :raises ValidationError: If business not found.
    """
    try:
        profile = BusinessProfile.objects.get(id=business_id, is_deleted=False)
    except (BusinessProfile.DoesNotExist, ValueError):
        raise ValidationError(f"BusinessProfile '{business_id}' not found.")

    with transaction.atomic():
        if status:
            profile.status = status
        if verification_status:
            profile.verification_status = verification_status

        profile.save()

        if admin_user:
            record_audit_log(
                admin=admin_user,
                action='MODERATE_BUSINESS',
                entity='BusinessProfile',
                entity_id=str(profile.id),
                result='SUCCESS',
                reason=f"Status: {profile.status}, Verification: {profile.verification_status}"
            )

    return profile
