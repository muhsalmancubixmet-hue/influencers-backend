import uuid
from typing import Optional
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import User, UserRole
from apps.creators.models import CreatorProfile, ProfileStatus, CreatorService
from apps.businesses.models import BusinessProfile
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
            pitch=pitch_text
        )

        # Atomic database-level increment to prevent lost updates under concurrency (REQ-SEC-04)
        Campaign.objects.filter(id=campaign.id).update(
            applications_count=F('applications_count') + 1,
            updated_at=timezone.now()
        )
        campaign.refresh_from_db(fields=['applications_count', 'updated_at'])

    # Wire automated notification trigger on new bid (REQ-NOTIF-02)
    try:
        from apps.common.api.v1.services import create_user_notification
        from apps.common.models import NotificationKind
        if campaign.business and campaign.business.user:
            create_user_notification(
                recipient=campaign.business.user,
                title=f"New Proposal for {campaign.title}",
                message=f"Creator @{creator.handle} submitted a collaboration proposal.",
                kind=NotificationKind.CAMPAIGN
            )
    except Exception:
        pass

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

    # Wire automated notification trigger on inquiry message reply (REQ-NOTIF-02)
    try:
        from apps.common.api.v1.services import create_user_notification
        from apps.common.models import NotificationKind
        target_recipient = (
            inquiry.business.user
            if (inquiry.creator and sender == inquiry.creator.user)
            else (inquiry.creator.user if inquiry.creator else None)
        )
        sender_label = sender.get_full_name() or sender.username
        if target_recipient and target_recipient != sender:
            create_user_notification(
                recipient=target_recipient,
                title=f"New Message: {inquiry.subject}",
                message=f"You received a new message from {sender_label}.",
                kind=NotificationKind.USER
            )
    except Exception:
        pass

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


def create_public_inquiry(validated_data: dict, request_user: Optional[User] = None) -> Inquiry:
    """
    Process and record a public collaboration inquiry from an external client or brand.

    Provisions a guest or established Business account dynamically to satisfy
    relational tenancy boundaries, links requested service package details if provided,
    and registers the initial Inquiry thread and opening message.

    :param validated_data: Sanitized dictionary containing:
                           - 'creator_handle': Target creator handle, display name slug, or UUID.
                           - 'client_email': Contact email address of the inquiring client/brand.
                           - 'client_name': Name of the brand representative.
                           - 'company_name': Optional trade or organization name.
                           - 'client_phone': Optional telephone contact number.
                           - 'subject': Campaign or proposal headline.
                           - 'message': Detailed deliverables brief or collaboration proposal.
                           - 'budget': Optional indicated compensation amount in major units.
                           - 'currency': Three-letter ISO 4217 currency code (default: 'INR').
                           - 'service_id': Optional package identifier or name from creator rate card.
    :param request_user: Optional authenticated User instance from the HTTP request.
    :return: Newly created Inquiry model instance.
    :raises ValidationError: If target creator cannot be found, is inactive, if client
                            email belongs to an active creator or admin account, or if
                            an unauthenticated caller attempts to use a registered password account.
    """
    from django.db.models import Q

    # Step 1: Resolve target creator profile with active status check and flexible identifier matching
    raw_ident = validated_data['creator_handle'].strip().lstrip('@')
    lookup = (
        Q(handle__iexact=raw_ident.lower()) |
        Q(display_name__iexact=raw_ident) |
        Q(display_name__iexact=raw_ident.replace('-', ' '))
    )
    try:
        parsed_uuid = uuid.UUID(raw_ident)
        lookup |= Q(id=parsed_uuid)
    except (ValueError, AttributeError):
        pass

    creator = CreatorProfile.objects.filter(
        lookup,
        status=ProfileStatus.ACTIVE,
        is_deleted=False
    ).first()
    if not creator:
        raise ValidationError(f"Creator '{raw_ident}' not found or is currently unavailable for collaborations.")

    # Step 2: Resolve optional Creator Service package from rate card
    service_package = None
    raw_service_id = validated_data.get('service_id')
    if raw_service_id:
        s_lookup = Q(creator=creator, is_active=True, is_deleted=False)
        try:
            s_uuid = uuid.UUID(str(raw_service_id).strip())
            service_package = CreatorService.objects.filter(s_lookup, id=s_uuid).first()
        except (ValueError, AttributeError):
            service_package = CreatorService.objects.filter(s_lookup, name__iexact=str(raw_service_id).strip()).first()

    # Step 3: Resolve or provision originating client User and BusinessProfile (Rule 5: No Auth Shortcuts & Tenant Boundaries)
    email = validated_data['client_email'].strip().lower()
    client_name = validated_data.get('client_name', '').strip()
    company_name = validated_data.get('company_name', '').strip() or client_name or "Client Brand"
    client_phone = validated_data.get('client_phone', '').strip()

    with transaction.atomic():
        # Anti-Account Hijacking (REQ-SEC-03): Guard against impersonating existing accounts
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if existing_user.role != UserRole.BUSINESS:
                raise ValidationError(
                    f"The email '{email}' is registered as an existing {existing_user.get_role_display()} account. "
                    "Please sign in to your workspace or provide a dedicated business email."
                )

            # If the account has an established password, anonymous callers cannot impersonate it
            if existing_user.has_usable_password():
                if not request_user or not request_user.is_authenticated or request_user.email.lower() != email:
                    raise ValidationError(
                        "An account with this email address already exists. "
                        "Please log in to your account to send collaboration inquiries."
                    )
            user = existing_user
        else:
            # Provision a new guest business identity
            user_base = email.split('@')[0]
            unique_suffix = str(uuid.uuid4())[:6]
            username = f"{user_base}_{unique_suffix}" if User.objects.filter(username=user_base).exists() else user_base
            user = User.objects.create(
                username=username,
                email=email,
                first_name=client_name,
                role=UserRole.BUSINESS,
                is_active=True
            )
            user.set_unusable_password()
            user.save()

        # Ensure BusinessProfile exists and is linked
        business_profile, _ = BusinessProfile.objects.get_or_create(
            user=user,
            defaults={
                'company_name': company_name,
                'contact_name': client_name or company_name,
                'business_type': 'Brand Client',
                'contact_email': email,
                'contact_phone': client_phone,
                'status': 'ACTIVE',
            }
        )

        # Step 4: Compute initial financial budget
        raw_budget = validated_data.get('budget')
        if raw_budget:
            budget_cents = int(raw_budget) * 100
        elif service_package and service_package.starting_price_cents:
            budget_cents = service_package.starting_price_cents
        else:
            budget_cents = None

        currency = validated_data.get('currency') or (service_package.currency if service_package else 'INR')

        # Step 5: Format initial message body including selected service details
        base_message = validated_data['message'].strip()
        if service_package:
            price_display = f"{service_package.currency} {service_package.starting_price_cents // 100}"
            service_annotation = f"\n\n[Selected Package: {service_package.name} ({price_display})]"
            initial_body = f"{base_message}{service_annotation}"
        else:
            initial_body = base_message

        # Step 6: Create the primary collaboration Inquiry thread
        inquiry = Inquiry.objects.create(
            business=business_profile,
            creator=creator,
            subject=validated_data['subject'].strip(),
            budget_cents=budget_cents,
            currency=currency,
            status=InquiryStatus.NEW
        )

        # Step 7: Append opening communication message to thread
        InquiryMessage.objects.create(
            inquiry=inquiry,
            sender=user,
            body=initial_body,
            is_read=False
        )

        # Step 8: Audit log creation
        record_audit_log(
            admin=user,
            action='CREATE_INQUIRY',
            entity='Inquiry',
            entity_id=str(inquiry.id),
            result='SUCCESS',
            reason=f"Public inquiry from {company_name} to @{creator.handle}"
        )

        # Step 9: Wire automated notification to creator (REQ-NOTIF-02)
        try:
            from apps.common.api.v1.services import create_user_notification
            from apps.common.models import NotificationKind
            if creator.user:
                create_user_notification(
                    recipient=creator.user,
                    title=f"New Collaboration Inquiry: {inquiry.subject}",
                    message=f"Brand {company_name} submitted a collaboration proposal.",
                    kind=NotificationKind.CAMPAIGN
                )
        except Exception:
            pass

    return inquiry

