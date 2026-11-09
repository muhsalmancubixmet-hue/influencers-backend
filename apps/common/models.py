import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class BaseModel(models.Model):
    """
    Abstract base model providing UUID primary key, audit timestamps, 
    and soft-delete capabilities for all persistent entities in the SaaS platform.
    
    All domain models across apps should inherit from BaseModel to maintain
    uniform identity, timestamp tracking, and non-destructive record deletion.
    """

    # Globally unique identifier (UUIDv4) preventing sequential ID enumeration attacks
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID primary key for the entity."
    )

    # Immutable creation timestamp in UTC set automatically on entity creation
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this record was originally created."
    )

    # Mutable last-updated timestamp in UTC updated automatically on entity modification
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last modified."
    )

    # Boolean flag indicating whether the record has been logically soft-deleted
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether this record is soft-deleted."
    )

    # Timestamp indicating exactly when the logical deletion occurred
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when soft deletion occurred, or null if active."
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def soft_delete(self) -> None:
        """
        Logically mark the record as deleted without purging physical data from the database.
        
        Updates `is_deleted` flag to True and records the current UTC timestamp into `deleted_at`.
        
        :return: None
        :raises django.db.DatabaseError: If database persistence fails during save.
        """
        # Step 1: Update logical deletion flags
        self.is_deleted = True
        self.deleted_at = timezone.now()

        # Step 2: Persist state to database
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

    def restore(self) -> None:
        """
        Restore a previously soft-deleted record back into active visibility.
        
        Resets `is_deleted` flag to False and clears `deleted_at` timestamp.
        
        :return: None
        :raises django.db.DatabaseError: If database persistence fails during save.
        """
        # Step 1: Clear logical deletion flags
        self.is_deleted = False
        self.deleted_at = None

        # Step 2: Persist restored state to database
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])


class SocialPlatform(BaseModel):
    """
    Master registry of supported social networks and channels.
    
    Configured by platform administrators to dictate which social channels creators can connect,
    whether OAuth authentication is supported, and which icon/brand color to display in UI.
    """

    # Brand title of the social network (e.g. 'Instagram', 'YouTube', 'TikTok')
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Brand name of the social platform."
    )

    # URL-friendly slug used for routing, API matching, and identification
    slug = models.SlugField(
        max_length=120,
        unique=True,
        help_text="URL-safe unique identifier for the social network."
    )

    # Identifier for the Lucide or SVG icon rendered in frontend user interfaces
    icon_name = models.CharField(
        max_length=50,
        blank=True,
        default='Share2',
        help_text="Name of the frontend icon component representing this platform."
    )

    # Hexadecimal CSS color code for platform branding (e.g. '#E1306C' for Instagram)
    color_code = models.CharField(
        max_length=20,
        default='#1f9e96',
        help_text="Hex color code used for badges and UI accents."
    )

    # Administrative toggle enabling creators to connect accounts from this platform
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether creators can currently link accounts from this network."
    )

    # Boolean flag indicating whether automated OAuth2 token exchange is enabled
    supports_oauth = models.BooleanField(
        default=False,
        help_text="True if automated OAuth token handshake is implemented for this platform."
    )

    # Boolean flag indicating whether live metric synchronization via external API is active
    supports_api = models.BooleanField(
        default=False,
        help_text="True if follower/engagement sync via official platform API is supported."
    )

    class Meta:
        verbose_name = 'Social Platform'
        verbose_name_plural = 'Social Platforms'
        ordering = ['name']

    def __str__(self) -> str:
        """
        String representation of the social platform.
        
        :return: Platform name.
        """
        return self.name

    def save(self, *args, **kwargs) -> None:
        """
        Auto-populate slug if missing before persisting.
        
        :param args: Positional arguments for save.
        :param kwargs: Keyword arguments for save.
        :return: None
        """
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class PlatformRequestStatus(models.TextChoices):
    """Moderation status choices for user-submitted platform requests."""
    PENDING = 'PENDING', 'Pending Review'
    APPROVED = 'APPROVED', 'Approved & Scheduled'
    REJECTED = 'REJECTED', 'Rejected'


class PlatformRequest(BaseModel):
    """
    Creator-submitted request for a new social network to be added to the platform.
    
    Allows creators to petition for regional or specialized social channels
    which admins can review, approve, or reject from the control panel.
    """

    # The creator user account who submitted the request
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='platform_requests',
        help_text="The creator account who petitioned for this platform."
    )

    # The title of the requested social platform (e.g. 'ShareChat', 'Bluesky')
    platform_name = models.CharField(
        max_length=100,
        help_text="Title of the unlisted social platform requested."
    )

    # URL to the creator's live profile on the requested platform
    profile_url = models.URLField(
        help_text="URL to the creator's profile on the requested platform."
    )

    # Creator's explanation of how this platform benefits their audience reach
    note = models.TextField(
        blank=True,
        help_text="Creator's rationale or audience reach notes."
    )

    # Moderation status tracking staff triage of the request
    status = models.CharField(
        max_length=20,
        choices=PlatformRequestStatus.choices,
        default=PlatformRequestStatus.PENDING,
        db_index=True,
        help_text="Current moderation state of this integration request."
    )

    # The administrative staff user who approved or rejected this petition
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_platform_requests',
        help_text="Staff administrator who evaluated this request."
    )

    # Timestamp recording exactly when moderation decision took place
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when this request was reviewed."
    )

    class Meta:
        verbose_name = 'Platform Request'
        verbose_name_plural = 'Platform Requests'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of the platform request.
        
        :return: Formatted request summary.
        """
        return f"Platform Request: {self.platform_name} by {self.requested_by.email} ({self.status})"


class ServiceType(BaseModel):
    """
    Standardized marketplace deliverable catalog archetype.
    
    Defines deliverable package templates (e.g. 'Instagram Reel (60s)', 'YouTube Dedicated Video')
    with benchmark pricing to guide creators and brands during service configuration.
    """

    # Display title of the deliverable service package
    name = models.CharField(
        max_length=150,
        help_text="Standard title of the service package (e.g. 'Instagram Reel (60s)')."
    )

    # Associated social network platform (or null if platform-agnostic such as UGC / Photography)
    platform = models.ForeignKey(
        SocialPlatform,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_types',
        help_text="Parent social channel, or null for cross-platform services."
    )

    # Benchmark average market price in smallest currency denomination (cents/paise)
    avg_price_cents = models.PositiveIntegerField(
        help_text="Benchmark average market price in smallest currency unit (e.g. paise/cents)."
    )

    # Standard three-letter ISO 4217 currency code
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code."
    )

    # Standardized specification of included assets and turnaround expectations
    deliverables_template = models.TextField(
        help_text="Default deliverables specification (e.g. '1 vertical video, raw B-roll, 2 revisions')."
    )

    # Administrative visibility toggle controlling availability in creator service builder
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether creators can select this service template."
    )

    class Meta:
        verbose_name = 'Service Type'
        verbose_name_plural = 'Service Types'
        ordering = ['name']

    def __str__(self) -> str:
        """
        String representation of service type.
        
        :return: Service name and platform.
        """
        platform_name = self.platform.name if self.platform else "Cross-platform"
        return f"{self.name} [{platform_name}]"


class PlatformSetting(BaseModel):
    """
    Dynamic configuration store for system-wide branding, security, email, and marketplace rules.
    
    Enables administrators to adjust operational policies (e.g. maintenance mode, commissions,
    session lengths) without deploying code modifications.
    """

    # Functional section grouping this configuration parameter
    section = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Functional section (e.g. 'general', 'branding', 'email', 'security', 'marketplace')."
    )

    # Unique configuration parameter key used for lookup in code
    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique configuration key identifier (e.g. 'platform_commission_percent')."
    )

    # Arbitrary structured configuration value persisted as native JSON
    value_json = models.JSONField(
        help_text="JSON-serialized setting payload accommodating booleans, numbers, strings, or objects."
    )

    # Administrative documentation explaining the purpose and valid values for this setting
    description = models.TextField(
        blank=True,
        help_text="Human-readable explanation of how this setting influences system behavior."
    )

    class Meta:
        verbose_name = 'Platform Setting'
        verbose_name_plural = 'Platform Settings'
        ordering = ['section', 'key']

    def __str__(self) -> str:
        """
        String representation of setting parameter.
        
        :return: Section and key identifier.
        """
        return f"Setting [{self.section}] {self.key}"


class MediaType(models.TextChoices):
    """Classification of digital media assets uploaded to the platform."""
    IMAGE = 'IMAGE', 'Standard Image'
    VIDEO = 'VIDEO', 'Video File'
    AVATAR = 'AVATAR', 'Profile Avatar'
    COVER = 'COVER', 'Profile Cover Photo'
    DOCUMENT = 'DOCUMENT', 'Document / ID Verification'


class MediaAsset(BaseModel):
    """
    Central registry of digital media assets stored on the platform's CDN.
    
    Tracks asset provenance, file types, storage size, and CDN access URLs
    across portfolio content, avatars, campaign deliverables, and verification evidence.
    """

    # The user account that uploaded this digital asset
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_media_assets',
        help_text="User identity who originally uploaded this asset."
    )

    # Original sanitized file name of the uploaded asset
    file_name = models.CharField(
        max_length=255,
        help_text="Original filename as uploaded by client."
    )

    # Classification type distinguishing videos, images, avatars, and documents
    file_type = models.CharField(
        max_length=20,
        choices=MediaType.choices,
        db_index=True,
        help_text="Classification type of the media file."
    )

    # Physical binary size of the asset in bytes for storage quota accounting
    file_size_bytes = models.BigIntegerField(
        help_text="Exact file size in bytes used for tenant storage quota calculations."
    )

    # Canonical HTTPS URL on the Content Delivery Network where the asset is served
    cdn_url = models.URLField(
        max_length=500,
        help_text="Canonical public CDN URL serving the media asset."
    )

    # Standard Internet media MIME type (e.g. 'image/jpeg', 'video/mp4')
    mime_type = models.CharField(
        max_length=100,
        help_text="MIME content type header (e.g. 'image/webp', 'video/mp4')."
    )

    class Meta:
        verbose_name = 'Media Asset'
        verbose_name_plural = 'Media Assets'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of media asset.
        
        :return: Filename and file type.
        """
        return f"{self.file_name} ({self.file_type})"


class TicketPriority(models.TextChoices):
    """Urgency severity classification for support tickets."""
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    URGENT = 'URGENT', 'Urgent'


class TicketStatus(models.TextChoices):
    """Operational triage and resolution status for support helpdesk tickets."""
    OPEN = 'OPEN', 'Open'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    WAITING = 'WAITING', 'Waiting on Customer'
    RESOLVED = 'RESOLVED', 'Resolved'
    CLOSED = 'CLOSED', 'Closed'


class SupportTicket(BaseModel):
    """
    Customer service helpdesk ticket submitted by creators or brand businesses.
    
    Tracks inbound support issues, category triage, urgency priority, operational status,
    and staff assignment for issue resolution.
    """

    # User identity who submitted the helpdesk ticket
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_tickets',
        help_text="The creator or brand user who opened this support ticket."
    )

    # Brief headline summarizing the customer issue
    subject = models.CharField(
        max_length=200,
        help_text="Short summary headline describing the inquiry or incident."
    )

    # Departmental problem classification (e.g. 'Billing', 'Campaign Dispute', 'Verification', 'Technical')
    category = models.CharField(
        max_length=50,
        help_text="Operational department classification (e.g. 'Billing', 'Campaign Dispute')."
    )

    # Severity priority level dictating escalation response SLAs
    priority = models.CharField(
        max_length=20,
        choices=TicketPriority.choices,
        default=TicketPriority.MEDIUM,
        db_index=True,
        help_text="Urgency level governing resolution response SLA."
    )

    # Current lifecycle state of ticket triage and resolution
    status = models.CharField(
        max_length=20,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True,
        help_text="Operational lifecycle state of this support ticket."
    )

    # Support agent or staff administrator assigned to resolve the ticket
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        help_text="Staff administrator or support agent assigned to handle this ticket."
    )

    class Meta:
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of the support ticket.
        
        :return: Ticket ID prefix, subject, and status.
        """
        return f"Ticket #{str(self.id)[:8]}: {self.subject} [{self.status}]"


class TicketMessage(BaseModel):
    """
    Chronological threaded message or internal administrative note within a SupportTicket.
    
    Supports communication between customers and support staff, as well as private
    internal notes invisible to end customers for staff coordination.
    """

    # Parent helpdesk ticket containing this conversation thread
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="The parent support ticket containing this reply or note."
    )

    # Author user who posted this message or note
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ticket_messages',
        help_text="User identity who authored this reply or internal note."
    )

    # Flag indicating whether the message author is an authenticated staff member
    is_staff = models.BooleanField(
        default=False,
        help_text="True if the message author holds staff administrative privileges."
    )

    # Private internal communication flag (hidden from public customer view)
    is_internal_note = models.BooleanField(
        default=False,
        help_text="True if private internal note invisible to customer, visible only to staff."
    )

    # Message text content containing problem details, guidance, or internal discussion
    body = models.TextField(
        help_text="Text content of the customer reply or staff investigation note."
    )

    # Optional URL to an attached screenshot, log file, or document
    attachment_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Optional URL to uploaded screenshot or diagnostic attachment."
    )

    class Meta:
        verbose_name = 'Ticket Message'
        verbose_name_plural = 'Ticket Messages'
        ordering = ['created_at']

    def __str__(self) -> str:
        """
        String representation of ticket message.
        
        :return: Author email, ticket reference, and note classification.
        """
        note_tag = " [INTERNAL NOTE]" if self.is_internal_note else ""
        return f"Message by {self.author.email} on #{str(self.ticket.id)[:8]}{note_tag}"


class AuditLog(BaseModel):
    """
    Immutable compliance audit ledger recording sensitive administrative and security actions.
    
    Captures who performed what action, against which entity, from which network IP,
    along with the outcome and operational justification.
    """

    # Staff administrator or superuser who executed the monitored action
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_audit_logs',
        help_text="Staff administrator who performed this operational or administrative action."
    )

    # Standardized verb identifying the action (e.g. 'SUSPEND_USER', 'REFUND_PAYMENT', 'CHANGE_ROLE')
    action = models.CharField(
        max_length=100,
        help_text="Standardized operational action verb (e.g. 'SUSPEND_USER', 'REFUND_PAYMENT')."
    )

    # Target entity domain model name affected (e.g. 'CreatorProfile', 'Payment', 'Campaign')
    entity = models.CharField(
        max_length=100,
        help_text="Domain model or resource name affected by the action."
    )

    # Primary key identifier of the target entity affected
    entity_id = models.CharField(
        max_length=100,
        help_text="Primary key identifier of the targeted resource entity."
    )

    # Client IP address originating the request for forensic tracing
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Client IPv4 or IPv6 address originating the administrative request."
    )

    # Client browser or API client user agent string
    user_agent = models.TextField(
        blank=True,
        help_text="HTTP User-Agent header string of the client software."
    )

    # Result outcome status of the monitored operation (e.g. 'SUCCESS', 'FAILED', 'BLOCKED')
    result = models.CharField(
        max_length=20,
        default='SUCCESS',
        help_text="Result status of the operation (e.g. 'SUCCESS', 'FAILED')."
    )

    # Business justification or administrative rationale for the action
    reason = models.TextField(
        blank=True,
        help_text="Administrative reasoning or compliance explanation for performing this action."
    )

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of the audit log entry.
        
        :return: Action verb, target entity, admin email, and timestamp.
        """
        admin_email = self.admin.email if self.admin else "System"
        return f"Audit: {self.action} on {self.entity}:{self.entity_id} by {admin_email}"


class NotificationKind(models.TextChoices):
    """Categorical classification of platform notifications."""
    SYSTEM = 'SYSTEM', 'System Alert'
    USER = 'USER', 'User Account Notice'
    CAMPAIGN = 'CAMPAIGN', 'Campaign Marketplace Event'
    VERIFICATION = 'VERIFICATION', 'Creator Verification Update'


class NotificationStatus(models.TextChoices):
    """Transmission and publication status of notifications."""
    DRAFT = 'DRAFT', 'Draft'
    SCHEDULED = 'SCHEDULED', 'Scheduled'
    SENT = 'SENT', 'Sent / Published'


class Notification(BaseModel):
    """
    Platform broadcast announcement or direct transactional user notification.
    
    Supports broadcast messaging targeted by audience criteria (e.g. 'All influencers',
    'All brands') or direct point-to-point alerts targeted to an individual recipient.
    """

    # Specific recipient user account, or null if globally broadcast to an entire audience
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Direct recipient user, or null if broadcast to target audience segment."
    )

    # Notification headline displayed in notification trays and bell icons
    title = models.CharField(
        max_length=200,
        help_text="Headline title of the notification message."
    )

    # Full body markdown or plaintext message content
    message = models.TextField(
        help_text="Full notification text content or announcement body."
    )

    # Functional category of the notification
    kind = models.CharField(
        max_length=20,
        choices=NotificationKind.choices,
        default=NotificationKind.SYSTEM,
        help_text="Functional category classification of the notice."
    )

    # Audience filter tag for broadcast notifications (e.g. 'All influencers', 'All brands')
    audience = models.CharField(
        max_length=50,
        blank=True,
        help_text="Audience segmentation target (e.g. 'All influencers', 'All brands')."
    )

    # Optional future UTC timestamp for scheduled broadcasts
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled publication time for delayed broadcast announcements."
    )

    # Publishing lifecycle status (draft, scheduled, sent)
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.SENT,
        help_text="Publication lifecycle status."
    )

    # Read status indicator for recipient inbox UI
    is_read = models.BooleanField(
        default=False,
        help_text="True if the recipient user has viewed or dismissed this notification."
    )

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of the notification.
        
        :return: Title, recipient or audience, and status.
        """
        target = self.recipient.email if self.recipient else f"Audience: {self.audience or 'Global'}"
        return f"Notification: {self.title} -> {target} [{self.status}]"