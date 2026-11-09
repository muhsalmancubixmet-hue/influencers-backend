import uuid
from typing import Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.creators.models import CreatorProfile
from apps.campaigns.models import (
    Campaign,
    CampaignBid,
    CampaignStatus,
    Requirement,
    Inquiry,
    InquiryStatus,
    InquiryMessage
)
from apps.common.api.v1.services import record_audit_log


def apply_to_campaign(
    campaign_id: str,
    creator: CreatorProfile,
    proposed_fee_cents: int,
    pitch_text: str
) -> CampaignBid:
    """
    Submit a creator bid application to an open campaign.
    
    Ensures campaign is accepting applications and creator hasn't already applied.
    Increments campaign applications_count atomically.
    
    :param campaign_id: UUID of target Campaign.
    :param creator: CreatorProfile submitting application.
    :param proposed_fee_cents: Creator's proposed compensation in smallest currency unit.
    :param pitch_text: Narrative proposal.
    :return: Created CampaignBid.
    :raises ValidationError: If campaign closed or already applied.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id, is_deleted=False)
    except (Campaign.DoesNotExist, ValueError, ValidationError):
        raise ValidationError(f"Campaign '{campaign_id}' not found.")

    if campaign.status not in [CampaignStatus.PUBLISHED, CampaignStatus.APPLICATIONS]:
        raise ValidationError("This campaign is not currently accepting applications.")

    if CampaignBid.objects.filter(campaign=campaign, creator=creator, is_deleted=False).exists():
        raise ValidationError("You have already submitted an application to this campaign.")

    with transaction.atomic():
        bid = CampaignBid.objects.create(
            campaign=campaign,
            creator=creator,
            proposed_fee_cents=proposed_fee_cents,
            pitch_text=pitch_text
        )

        campaign.applications_count += 1
        campaign.save(update_fields=['applications_count', 'updated_at'])

    return bid


def send_inquiry_reply(
    inquiry_id: str,
    sender: User,
    body: str,
    offer_price_cents: Optional[int] = None
) -> InquiryMessage:
    """
    Append a reply message to an existing inquiry thread and refresh timestamps.
    
    :param inquiry_id: UUID of Inquiry.
    :param sender: User sending message.
    :param body: Text content.
    :param offer_price_cents: Optional updated monetary deal price.
    :return: Created InquiryMessage.
    :raises ValidationError: If inquiry not found.
    """
    try:
        inquiry = Inquiry.objects.get(id=inquiry_id, is_deleted=False)
    except (Inquiry.DoesNotExist, ValueError, ValidationError):
        raise ValidationError(f"Inquiry '{inquiry_id}' not found.")

    with transaction.atomic():
        message = InquiryMessage.objects.create(
            inquiry=inquiry,
            sender=sender,
            body=body
        )

        if offer_price_cents is not None:
            inquiry.budget_cents = offer_price_cents
            inquiry.save(update_fields=['budget_cents', 'updated_at'])
        else:
            inquiry.save(update_fields=['updated_at'])

    return message


def moderate_campaign(
    campaign_id: str,
    is_featured: Optional[bool] = None,
    status: Optional[str] = None,
    admin_user: Optional[User] = None
) -> Campaign:
    """
    Moderate campaign status or featured flag with compliance audit.
    
    :param campaign_id: UUID of Campaign.
    :param is_featured: Optional boolean toggle.
    :param status: Optional CampaignStatus.
    :param admin_user: Staff User performing action.
    :return: Updated Campaign.
    :raises ValidationError: If campaign not found.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id, is_deleted=False)
    except (Campaign.DoesNotExist, ValueError, ValidationError):
        raise ValidationError(f"Campaign '{campaign_id}' not found.")

    with transaction.atomic():
        if is_featured is not None:
            campaign.is_featured = is_featured
        if status:
            campaign.status = status

        campaign.save()

        if admin_user:
            record_audit_log(
                admin=admin_user,
                action='MODERATE_CAMPAIGN',
                entity='Campaign',
                entity_id=str(campaign.id),
                result='SUCCESS',
                reason=f"Status: {campaign.status}, Featured: {campaign.is_featured}"
            )

    return campaign


def moderate_requirement(
    requirement_id: str,
    status: str,
    admin_user: Optional[User] = None
) -> Requirement:
    """
    Moderate open requirement status with audit log.
    
    :param requirement_id: UUID of Requirement.
    :param status: New RequirementStatus.
    :param admin_user: Staff User.
    :return: Updated Requirement.
    """
    try:
        req = Requirement.objects.get(id=requirement_id, is_deleted=False)
    except (Requirement.DoesNotExist, ValueError, ValidationError):
        raise ValidationError(f"Requirement '{requirement_id}' not found.")

    with transaction.atomic():
        req.status = status
        req.save(update_fields=['status', 'updated_at'])

        if admin_user:
            record_audit_log(
                admin=admin_user,
                action='MODERATE_REQUIREMENT',
                entity='Requirement',
                entity_id=str(req.id),
                result='SUCCESS',
                reason=f"Status changed to {status}"
            )

    return req


def create_public_inquiry(validated_data: dict) -> Inquiry:
    """
    Process and record a public collaboration inquiry from an external client/brand.
    
    Provisions a guest or established Business account dynamically to satisfy
    relational tenancy boundaries, then registers the Inquiry thread and first message.
    
    :param validated_data: Sanitized dictionary containing creator_handle, client_email,
                           client_name, company_name, subject, message, and budget.
    :return: Newly created Inquiry model instance.
    :raises ValidationError: If the target creator cannot be found or is inactive.
    """
    from apps.accounts.models import User, UserRole
    from apps.businesses.models import BusinessProfile

    # Step 1: Resolve target creator profile (by UUID or handle)
    raw_ident = validated_data['creator_handle'].strip().lstrip('@')
    from django.db.models import Q
    lookup = Q(handle__iexact=raw_ident.lower())
    try:
        parsed_uuid = uuid.UUID(raw_ident)
        lookup |= Q(id=parsed_uuid)
    except (ValueError, AttributeError):
        pass

    creator = CreatorProfile.objects.filter(lookup, is_deleted=False).first()
    if not creator:
        raise ValidationError(f"Creator '{raw_ident}' not found.")

    # Step 2: Resolve or provision originating client User and BusinessProfile
    email = validated_data['client_email'].strip().lower()
    client_name = validated_data.get('client_name', '').strip()
    company_name = validated_data.get('company_name', '').strip() or client_name or "Client Brand"

    with transaction.atomic():
        user = User.objects.filter(email=email).first()
        if not user:
            user = User.objects.create(
                username=email.split('@')[0] + "_" + str(uuid.uuid4())[:6] if User.objects.filter(username=email.split('@')[0]).exists() else email.split('@')[0],
                email=email,
                first_name=client_name,
                role=UserRole.BUSINESS,
                is_active=True
            )
            user.set_unusable_password()
            user.save()

        # Ensure business profile exists for this client identity
        business_profile = BusinessProfile.objects.filter(user=user).first()
        if not business_profile:
            business_profile = BusinessProfile.objects.create(
                user=user,
                company_name=company_name,
                contact_name=client_name or company_name,
                business_type="Brand Client",
                contact_email=email,
                contact_phone=validated_data.get('client_phone', '')
            )

        # Step 3: Compute initial financial budget
        raw_budget = validated_data.get('budget')
        budget_cents = (int(raw_budget) * 100) if raw_budget else None
        currency = validated_data.get('currency', 'INR')

        # Step 4: Create the primary collaboration Inquiry thread
        inquiry = Inquiry.objects.create(
            business=business_profile,
            creator=creator,
            subject=validated_data['subject'].strip(),
            budget_cents=budget_cents,
            currency=currency,
            status=InquiryStatus.NEW
        )

        # Step 5: Append opening communication message to thread
        InquiryMessage.objects.create(
            inquiry=inquiry,
            sender=user,
            body=validated_data['message'].strip(),
            is_read=False
        )

        # Step 6: Audit log creation
        record_audit_log(
            admin=user,
            action='CREATE_INQUIRY',
            entity='Inquiry',
            entity_id=str(inquiry.id),
            result='SUCCESS',
            reason=f"Public inquiry from {company_name} to @{creator.handle}"
        )

    return inquiry

