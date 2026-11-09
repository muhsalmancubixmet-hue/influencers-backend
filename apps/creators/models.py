from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class VerificationStatus(models.TextChoices):
    """Lifecycle status choices for creator account verification."""
    UNVERIFIED = 'UNVERIFIED', 'Unverified'
    PENDING = 'PENDING', 'Pending Verification'
    VERIFIED = 'VERIFIED', 'Verified'
    REJECTED = 'REJECTED', 'Verification Rejected'


class ProfileStatus(models.TextChoices):
    """Operational visibility status of the creator profile."""
    ACTIVE = 'ACTIVE', 'Active'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    PENDING = 'PENDING', 'Pending Review'


class CreatorProfile(BaseModel):
    """
    Public and marketplace identity profile for an influencer / creator.
    
    Houses core branding, verification status, regional preferences, and location links.
    Maintains a 1:1 relationship with the underlying User account.
    """

    # Link to the authenticated user holding the CREATOR tenancy role
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='creator_profile',
        help_text="Underlying user account holding the CREATOR tenant role."
    )

    # Public unique handle used in creator URLs (e.g. /@ananya)
    handle = models.CharField(
        max_length=80,
        unique=True,
        db_index=True,
        help_text="Unique URL-safe handle identifying the creator (e.g. 'ananya.travels')."
    )

    # Formatted display name shown across discovery, media kits, and proposals
    display_name = models.CharField(
        max_length=150,
        help_text="Public full name or brand pseudonym displayed across marketplace."
    )

    # Short headline pitch shown on creator preview cards (max 255 chars)
    bio = models.CharField(
        max_length=255,
        blank=True,
        help_text="Concise one-liner summary of content focus and creative angle."
    )

    # Long-form biography detailing collaboration experience and creative background
    about = models.TextField(
        blank=True,
        help_text="In-depth narrative describing past collaborations, awards, and approach."
    )

    # Public avatar image URL served from CDN
    photo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="CDN URL pointing to creator's avatar photograph."
    )

    # Wide cover/banner image URL served from CDN
    cover_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="CDN URL pointing to wide header cover banner."
    )

    # Primary hometown/headquarters location
    primary_location = models.ForeignKey(
        'taxonomies.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='creators_primary',
        help_text="Base hometown location node (city/country) of the creator."
    )

    # Current operating location (if traveling or temporarily relocated)
    current_location = models.ForeignKey(
        'taxonomies.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='creators_current',
        help_text="Current location if actively traveling or shooting abroad."
    )

    # Base pricing and invoice currency code (ISO 4217)
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code for rate calculations."
    )

    # Willingness to travel to brand shoot locations
    travel_available = models.BooleanField(
        default=False,
        help_text="True if creator accepts on-site campaigns requiring travel."
    )

    # Willingness to deliver remote UGC / digital assets worldwide
    remote_available = models.BooleanField(
        default=True,
        help_text="True if creator accepts remote collaborations worldwide."
    )

    # Official verification badge state
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
        db_index=True,
        help_text="Current verification badge status awarded by moderators."
    )

    # Operational status (moderated suspension or active state)
    status = models.CharField(
        max_length=20,
        choices=ProfileStatus.choices,
        default=ProfileStatus.ACTIVE,
        db_index=True,
        help_text="Operational lifecycle state (active, suspended, pending)."
    )

    # Calculated profile completeness score between 0 and 100 percent
    completion_percentage = models.PositiveSmallIntegerField(
        default=0,
        help_text="Calculated profile completeness metric (0-100%)."
    )

    # JSON dictionary storing user-configurable visibility, notification, and regional preferences
    preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom preferences including visibility toggles, notification filters, interface language, and timezone."
    )

    class Meta:
        verbose_name = 'Creator Profile'
        verbose_name_plural = 'Creator Profiles'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of creator profile.
        
        :return: Display name and handle.
        """
        return f"{self.display_name} (@{self.handle})"


class CreatorCategory(BaseModel):
    """
    Many-to-many relationship mapping creators to taxonomy categories.
    
    Allows a creator to belong to multiple verticals (e.g. Travel + Food + Culture).
    """

    # Target creator profile
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name='categories',
        help_text="The creator profile being classified."
    )

    # Target classification category
    category = models.ForeignKey(
        'taxonomies.Category',
        on_delete=models.CASCADE,
        related_name='creator_links',
        help_text="The taxonomy category vertical linked to this creator."
    )

    class Meta:
        verbose_name = 'Creator Category'
        verbose_name_plural = 'Creator Categories'
        constraints = [
            models.UniqueConstraint(fields=['creator', 'category'], name='creator_category_uniq')
        ]

    def __str__(self) -> str:
        """
        String representation of category assignment.
        
        :return: Handle and category name.
        """
        return f"@{self.creator.handle} -> {self.category.name}"


class CreatorLanguage(BaseModel):
    """
    Languages spoken or used in content creation by this creator.
    """

    # Target creator profile
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name='languages',
        help_text="The creator profile possessing this language proficiency."
    )

    # Standard ISO 639-1 two-letter language code (e.g. 'en', 'ml', 'hi')
    language_code = models.CharField(
        max_length=10,
        help_text="ISO 639 language code (e.g. 'en', 'ml', 'hi', 'ar')."
    )

    class Meta:
        verbose_name = 'Creator Language'
        verbose_name_plural = 'Creator Languages'
        constraints = [
            models.UniqueConstraint(fields=['creator', 'language_code'], name='creator_lang_uniq')
        ]

    def __str__(self) -> str:
        """
        String representation of language capability.
        
        :return: Handle and language code.
        """
        return f"@{self.creator.handle} -> {self.language_code}"


class CreatorServiceArea(BaseModel):
    """
    Geographic places where the creator is physically willing to accept on-site work.
    """

    # Target creator profile
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name='service_areas',
        help_text="The creator profile offering on-site coverage."
    )

    # Target covered geographic location
    location = models.ForeignKey(
        'taxonomies.Location',
        on_delete=models.CASCADE,
        related_name='served_by_creators',
        help_text="Geographic city, district, or region covered by creator."
    )

    class Meta:
        verbose_name = 'Creator Service Area'
        verbose_name_plural = 'Creator Service Areas'
        constraints = [
            models.UniqueConstraint(fields=['creator', 'location'], name='creator_area_uniq')
        ]

    def __str__(self) -> str:
        """
        String representation of service area.
        
        :return: Handle and location name.
        """
        return f"@{self.creator.handle} operates in {self.location.name}"


class SocialAccount(BaseModel):
    """
    Social channel account connected to a creator's profile.
    
    Stores handle, follower stats, engagement benchmarks, and sync timestamps.
    """

    # Target creator profile
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name='social_accounts',
        help_text="The creator account possessing this connected channel."
    )

    # Registered social network platform
    platform = models.ForeignKey(
        'common.SocialPlatform',
        on_delete=models.CASCADE,
        related_name='connected_accounts',
        help_text="The master social network platform definition."
    )

    # Channel username on the external network (e.g. 'ananya.travels')
    username = models.CharField(
        max_length=150,
        help_text="Username or channel identifier on the external social platform."
    )

    # Full canonical web URL to the creator's social page (supports long query/tracking parameters)
    profile_url = models.URLField(
        max_length=2000,
        help_text="Direct link to the creator's external channel profile."
    )

    # Current aggregate follower count on this platform
    followers_count = models.PositiveIntegerField(
        default=0,
        help_text="Total verified follower count."
    )

    # Current accounts followed count
    following_count = models.PositiveIntegerField(
        default=0,
        help_text="Total accounts followed on this network."
    )

    # Average percentage engagement rate (e.g. 5.40%)
    engagement_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.0,
        help_text="Engagement percentage rate (e.g. 5.40 for 5.40%)."
    )

    # Native platform verification badge indicator
    is_verified = models.BooleanField(
        default=False,
        help_text="True if this account carries a verified checkmark on the external network."
    )

    # Timestamp of the last metric pull from the platform API
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent automated data sync."
    )

    class Meta:
        verbose_name = 'Social Account'
        verbose_name_plural = 'Social Accounts'
        constraints = [
            models.UniqueConstraint(fields=['creator', 'platform'], name='creator_social_platform_uniq')
        ]

    def __str__(self) -> str:
        """
        String representation of social account.
        
        :return: Platform and username.
        """
        return f"{self.platform.name}: @{self.username} (@{self.creator.handle})"


class PortfolioMediaType(models.TextChoices):
    """Categorization of media formats in creator portfolio showcases."""
    REEL = 'REEL', 'Instagram / Social Reel'
    IMAGE = 'IMAGE', 'High-Res Photo'
    VIDEO = 'VIDEO', 'Long-form Video'
    UGC = 'UGC', 'User-Generated Content'
    ARTICLE = 'ARTICLE', 'Editorial / Article'


class PortfolioItem(BaseModel):
    """
    Curated showcase piece highlighting a creator's best brand collaboration or content work.
    """

    # Target creator profile
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name='portfolio_items',
        help_text="The creator profile showcasing this work."
    )

    # Title of the portfolio showcase piece
    title = models.CharField(
        max_length=200,
        help_text="Display title of the portfolio item."
    )

    # CDN URL for the preview image or video asset
    media_url = models.URLField(
        max_length=500,
        help_text="CDN URL pointing to the primary image or video showcase asset."
    )

    # Media deliverable format classification
    media_type = models.CharField(
        max_length=20,
        choices=PortfolioMediaType.choices,
        default=PortfolioMediaType.REEL,
        help_text="Format classification (Reel, Image, Video, UGC, Article)."
    )

    # Name of the client or brand who commissioned this work
    brand_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Client or brand name associated with this collaboration."
    )

    # Date when the project was published
    deliverable_date = models.DateField(
        null=True,
        blank=True,
        help_text="Original publication date of this piece."
    )

    # Viewership/impressions count achieved by this content piece
    views_count = models.PositiveIntegerField(
        default=0,
        help_text="Total verified views or impressions earned by this item."
    )

    # Visual tag or category label displayed on portfolio cards
    format_tag = models.CharField(
        max_length=50,
        blank=True,
        help_text="Badge tag shown on card (e.g. 'Reel', 'Travel', 'Fashion')."
    )

    # Narrative describing creative strategy, metrics, and brand results
    description = models.TextField(
        blank=True,
        help_text="Contextual description of the creative concept and campaign outcomes."
    )

    # Visual ordering position in the creator's portfolio grid
    order = models.PositiveIntegerField(
        default=0,
        help_text="Sorting rank within the creator's portfolio showcase."
    )

    class Meta:
        verbose_name = 'Portfolio Item'
        verbose_name_plural = 'Portfolio Items'
        ordering = ['order', '-created_at']

    def __str__(self) -> str:
        """
        String representation of portfolio item.
        
        :return: Title and creator handle.
        """
        return f"{self.title} (@{self.creator.handle})"


class CreatorService(BaseModel):
    """
    Configured service offering and rate card package sold by a creator.
    
    Examples: 'Instagram Reel (60s)', 'Full Brand Ambassador Package', 'UGC Raw Clips'.
    """

    # Target creator profile
    creator = models.ForeignKey(
        CreatorProfile,
        on_delete=models.CASCADE,
        related_name='services',
        help_text="The creator offering this package."
    )

    # Optional reference to the platform service template benchmark
    service_type = models.ForeignKey(
        'common.ServiceType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custom_offers',
        help_text="Underlying benchmark catalog template, or null for fully custom package."
    )

    # Title of the service package
    name = models.CharField(
        max_length=150,
        help_text="Title of the service offer (e.g. 'YouTube Short + Community Post')."
    )

    # Detailed scope of what is provided in this package
    description = models.TextField(
        blank=True,
        help_text="Summary of what the brand receives under this package."
    )

    # Bullet deliverables specification
    deliverables_spec = models.TextField(
        help_text="Itemized deliverables specification (e.g. '1 Reel, 2 Stories, Raw B-Roll')."
    )

    # Estimated delivery turnaround time in calendar days
    turnaround_days = models.PositiveSmallIntegerField(
        default=7,
        help_text="Estimated turnaround duration in calendar days."
    )

    # Minimum package fee stored in smallest currency denomination (cents/paise)
    starting_price_cents = models.PositiveIntegerField(
        default=0,
        help_text="Base package fee in smallest currency unit (paise/cents)."
    )

    # Three-letter currency code for rates
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code."
    )

    # Creator visibility toggle enabling or hiding this service
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this service offer is active and visible on public profile."
    )

    # Flag indicating whether price is unlisted and requires direct brand inquiry
    is_contact_for_price = models.BooleanField(
        default=False,
        help_text="True if pricing is hidden and requires direct negotiation."
    )

    class Meta:
        verbose_name = 'Creator Service'
        verbose_name_plural = 'Creator Services'
        ordering = ['name']

    def __str__(self) -> str:
        """
        String representation of creator service offer.
        
        :return: Service name and creator handle.
        """
        return f"{self.name} by @{self.creator.handle}"


class VerificationRequestKind(models.TextChoices):
    """The domain entity subject to verification review."""
    CREATOR = 'CREATOR', 'Creator Account Verification'
    SOCIAL = 'SOCIAL', 'Social Network Badge'
    BUSINESS = 'BUSINESS', 'Brand / Business Verification'


class VerificationRequestStatus(models.TextChoices):
    """Staff triage status for verification submissions."""
    PENDING = 'PENDING', 'Pending Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    INFO_REQUESTED = 'INFO_REQUESTED', 'Information Requested'


class VerificationRequest(BaseModel):
    """
    Identity verification submission queue item reviewed by moderators.
    
    Governs blue checkmark verification badges for creators, businesses, and social accounts.
    """

    # Type of verification being reviewed (creator profile, social link, or business)
    kind = models.CharField(
        max_length=20,
        choices=VerificationRequestKind.choices,
        default=VerificationRequestKind.CREATOR,
        help_text="Entity classification being verified."
    )

    # The user account seeking verification
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_requests',
        help_text="The applicant user account."
    )

    # Detailed notes or government ID documentation submitted by applicant
    detail_text = models.TextField(
        blank=True,
        help_text="Supporting documentation or links submitted for verification."
    )

    # Current adjudication status
    status = models.CharField(
        max_length=20,
        choices=VerificationRequestStatus.choices,
        default=VerificationRequestStatus.PENDING,
        db_index=True,
        help_text="Staff review status."
    )

    # Internal explanation or message relayed to applicant upon review
    admin_note = models.TextField(
        blank=True,
        help_text="Moderation explanation or feedback requested from applicant."
    )

    # The staff user who evaluated the application
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_verifications',
        help_text="Staff administrator who evaluated this request."
    )

    # Timestamp of final adjudication decision
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when verification decision was committed."
    )

    class Meta:
        verbose_name = 'Verification Request'
        verbose_name_plural = 'Verification Requests'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of verification request.
        
        :return: Applicant email, kind, and status.
        """
        return f"Verify [{self.kind}] {self.user.email}: {self.status}"
