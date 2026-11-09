from typing import Any, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.common.models import (
    PlatformRequest,
    PlatformRequestStatus,
    PlatformSetting,
    SupportTicket,
    TicketMessage,
    AuditLog,
    Notification,
    NotificationKind,
    NotificationStatus
)


def review_platform_request(request_id: str, new_status: str, reviewer: User) -> PlatformRequest:
    """
    Approve or reject a creator platform request with staff attribution.
    
    :param request_id: UUID of PlatformRequest.
    :param new_status: 'APPROVED' or 'REJECTED'.
    :param reviewer: Staff User performing review.
    :return: Updated PlatformRequest.
    :raises ValidationError: If request does not exist or status invalid.
    """
    try:
        req = PlatformRequest.objects.get(id=request_id, is_deleted=False)
    except (PlatformRequest.DoesNotExist, ValueError):
        raise ValidationError(f"PlatformRequest '{request_id}' not found.")

    if new_status not in [PlatformRequestStatus.APPROVED, PlatformRequestStatus.REJECTED]:
        raise ValidationError(f"Invalid review status: '{new_status}'.")

    with transaction.atomic():
        req.status = new_status
        req.reviewed_by = reviewer
        req.reviewed_at = timezone.now()
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

        if new_status == PlatformRequestStatus.APPROVED:
            from apps.common.models import SocialPlatform
            SocialPlatform.objects.get_or_create(
                name=req.platform_name,
                defaults={
                    'is_active': True,
                    'color_code': '#6366f1'
                }
            )

        record_audit_log(
            admin=reviewer,
            action='REVIEW_PLATFORM_REQUEST',
            entity='PlatformRequest',
            entity_id=str(req.id),
            reason=f"Platform request review: {new_status} for {req.platform_name}"
        )
    return req


def update_platform_setting(key: str, value_json: Any, updater: User) -> PlatformSetting:
    """
    Update a dynamic platform configuration setting and log an audit record.
    
    :param key: Unique setting identifier key.
    :param value_json: Updated JSON value payload.
    :param updater: Staff User updating setting.
    :return: Updated PlatformSetting.
    :raises ValidationError: If setting key does not exist.
    """
    try:
        setting = PlatformSetting.objects.get(key=key, is_deleted=False)
    except PlatformSetting.DoesNotExist:
        raise ValidationError(f"PlatformSetting with key '{key}' does not exist.")

    with transaction.atomic():
        setting.value_json = value_json
        setting.save(update_fields=['value_json', 'updated_at'])

        record_audit_log(
            admin=updater,
            action='UPDATE_PLATFORM_SETTING',
            entity='PlatformSetting',
            entity_id=str(setting.key),
            result='SUCCESS',
            reason=f"Updated configuration key '{key}'"
        )

    return setting


def add_ticket_message(
    ticket_id: str,
    author: User,
    body: str,
    is_staff: bool,
    is_internal_note: bool = False,
    attachment_url: str = ''
) -> TicketMessage:
    """
    Append a reply or internal staff note to a support ticket.
    
    :param ticket_id: UUID of the SupportTicket.
    :param author: User posting the message.
    :param body: Text content.
    :param is_staff: Whether author holds staff privileges.
    :param is_internal_note: True for private staff-only coordination note.
    :param attachment_url: Optional attachment URL.
    :return: Created TicketMessage.
    :raises ValidationError: If ticket not found.
    """
    try:
        ticket = SupportTicket.objects.get(id=ticket_id, is_deleted=False)
    except (SupportTicket.DoesNotExist, ValueError):
        raise ValidationError(f"SupportTicket '{ticket_id}' not found.")

    with transaction.atomic():
        message = TicketMessage.objects.create(
            ticket=ticket,
            author=author,
            is_staff=is_staff,
            is_internal_note=is_internal_note,
            body=body,
            attachment_url=attachment_url
        )

        # Update parent ticket updated_at
        ticket.save(update_fields=['updated_at'])

    return message


def record_audit_log(
    admin: Optional[User],
    action: str,
    entity: str,
    entity_id: str,
    request: Optional[Any] = None,
    result: str = 'SUCCESS',
    reason: str = ''
) -> AuditLog:
    """
    Persist an immutable audit trail entry for administrative compliance.
    
    :param admin: Staff user performing the action.
    :param action: Action verb (e.g. 'SUSPEND_USER', 'REFUND_PAYMENT').
    :param entity: Domain model name affected.
    :param entity_id: ID of the resource affected.
    :param request: Optional HTTP request for extracting IP and User-Agent.
    :param result: 'SUCCESS', 'FAILED', or 'BLOCKED'.
    :param reason: Administrative reasoning.
    :return: Persisted AuditLog instance.
    """
    ip_address = None
    user_agent = ''

    if request is not None:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    return AuditLog.objects.create(
        admin=admin,
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        ip_address=ip_address,
        user_agent=user_agent,
        result=result,
        reason=reason
    )


def dispatch_broadcast_notification(
    title: str,
    message: str,
    audience: str = 'All users',
    kind: str = NotificationKind.SYSTEM,
    scheduled_at: Optional[timezone.datetime] = None
) -> Notification:
    """
    Create and dispatch a platform broadcast announcement.
    
    :param title: Notification headline.
    :param message: Full message content.
    :param audience: Target audience category tag.
    :param kind: Notification kind.
    :param scheduled_at: Optional scheduled future publication timestamp.
    :return: Created Notification instance.
    """
    status_choice = NotificationStatus.SCHEDULED if (scheduled_at and scheduled_at > timezone.now()) else NotificationStatus.SENT
    return Notification.objects.create(
        recipient=None,
        title=title,
        message=message,
        kind=kind,
        audience=audience,
        scheduled_at=scheduled_at,
        status=status_choice
    )


def create_creator_platform_request(
    user: User,
    platform_name: str,
    profile_url: str = '',
    note: str = ''
) -> PlatformRequest:
    """
    Submit a platform petition request from an authenticated creator.
    
    Validates payload integrity and creates a pending review record for admin attention.
    
    :param user: Authenticated User initiating the request.
    :param platform_name: Title of requested unlisted platform.
    :param profile_url: Creator profile URL on the target platform.
    :param note: Contextual explanation or usage notes.
    :return: Created PlatformRequest instance.
    :raises ValidationError: If platform_name is empty.
    """
    # Step 1: Validate payload parameters
    clean_name = platform_name.strip()
    if not clean_name:
        raise ValidationError("Platform name is required.")

    # Check for duplicate pending request by the same user
    existing = PlatformRequest.objects.filter(
        requested_by=user,
        platform_name__iexact=clean_name,
        status=PlatformRequestStatus.PENDING,
        is_deleted=False
    ).first()
    if existing:
        return existing

    # Step 2: Atomic persistence and audit log entry
    with transaction.atomic():
        req = PlatformRequest.objects.create(
            requested_by=user,
            platform_name=clean_name,
            profile_url=profile_url.strip(),
            note=note.strip(),
            status=PlatformRequestStatus.PENDING
        )

        record_audit_log(
            admin=user,
            action='REQUEST_PLATFORM',
            entity='PlatformRequest',
            entity_id=str(req.id),
            result='SUCCESS',
            reason=f"Creator requested new platform: {clean_name}"
        )

    return req
