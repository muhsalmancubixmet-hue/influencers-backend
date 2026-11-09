from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class CampaignStatus(models.TextChoices):
    """Lifecycle progress state of a marketplace brand campaign."""
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    APPLICATIONS = 'APPLICATIONS', 'Accepting Applications'
    SHORTLISTED = 'SHORTLISTED', 'Bids Shortlisted'
    ACTIVE = 'ACTIVE', 'Active / In Production'
    CONTENT_SUBMITTED = 'CONTENT_SUBMITTED', 'Content Submitted'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class EscrowStatus(models.TextChoices):
    """Financial escrow protection status for the campaign budget."""
    PENDING = 'PENDING', 'Pending Funding'
    HELD = 'HELD', 'Held in Escrow'
    PARTIALLY_RELEASED = 'PARTIALLY_RELEASED', 'Partially Released'
    RELEASED = 'RELEASED', 'Released to Creators'
    REFUNDED = 'REFUNDED', 'Refunded to Business'


class Campaign(BaseModel):
    """
    Brand-funded marketing campaign posted to the Influencers.com marketplace.
    
    Houses creative brief, escrow financial security, target deliverables,
    creator quota, and application deadlines.
    """

    # Brand or business profile owning and financing this campaign
    business = models.ForeignKey(
        'businesses.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='campaigns',
        help_text="Brand organization funding and managing this campaign."
    )

    # Public headline title of the campaign (e.g. 'Monsoon in Munnar 4K Reels')
    title = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Commercial campaign title displayed across marketplace."
    )

    # Primary taxonomy category vertical linked to this brief
    category = models.ForeignKey(
        'taxonomies.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
        help_text="Taxonomy domain vertical (e.g. Travel, Food, Fashion)."
    )

    # Freeform human-readable location description (e.g. 'Munnar & Kochi, Kerala')
    location_text = models.CharField(
        max_length=150,
        blank=True,
        help_text="Descriptive location summary for campaign display."
    )

    # Structured geographic taxonomy node for GPS/radius matching
    location = models.ForeignKey(
        'taxonomies.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
        help_text="Specific geographic hub targeted for this campaign."
    )

    # Total allocated campaign budget in smallest currency unit (paise/cents)
    total_budget_cents = models.PositiveIntegerField(
        default=0,
        help_text="Total committed budget in smallest denomination (e.g. paise/cents)."
    )

    # Three-letter currency code (ISO 4217)
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code."
    )

    # Target number of creator slots available for hiring
    creators_needed = models.PositiveSmallIntegerField(
        default=1,
        help_text="Total number of creator collaboration slots."
    )

    # Cached counter tracking total proposals received from creators
    applications_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached counter of pitches/bids submitted by creators."
    )

    # Cutoff date after which new applications are automatically closed
    deadline = models.DateField(
        null=True,
        blank=True,
        help_text="Application submission deadline date."
    )

    # Operational lifecycle state of the campaign
    status = models.CharField(
        max_length=30,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT,
        db_index=True,
        help_text="Operational lifecycle state (draft, applications, active, completed)."
    )

    # Financial escrow security status of committed funds
    escrow_status = models.CharField(
        max_length=30,
        choices=EscrowStatus.choices,
        default=EscrowStatus.PENDING,
        db_index=True,
        help_text="Financial escrow status tracking deposit safety."
    )

    # Marketing goal and strategic objective of the campaign
    objective = models.TextField(
        blank=True,
        help_text="Campaign mission, key message, and marketing goals."
    )

    # Description of target consumer demographics and audience profile
    target_audience = models.TextField(
        blank=True,
        help_text="Desired audience profile, age brackets, and geographic focus."
    )

    # Specific required deliverables specification (e.g. '1 Reel (60s), 3 Stories, 30 days usage')
    deliverables_spec = models.TextField(
        help_text="Required creative deliverables and content specifications."
    )

    # Promotional flag promoting this campaign to the top of creator discovery
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Designates whether this campaign is pinned as a featured opportunity."
    )

    class Meta:
        verbose_name = 'Campaign'
        verbose_name_plural = 'Campaigns'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of campaign.
        
        :return: Campaign title and owning brand.
        """
        return f"{self.title} ({self.business.company_name})"


class RequirementStatus(models.TextChoices):
    """Moderation and lifecycle status for business requirement leads."""
    OPEN = 'OPEN', 'Open'
    FEATURED = 'FEATURED', 'Featured'
    HIDDEN = 'HIDDEN', 'Hidden'
    CLOSED = 'CLOSED', 'Closed'


class Requirement(BaseModel):
    """
    Public creator requirement brief posted by a business.
    
    Acts as a lightweight request-for-proposal on the public board,
    allowing verified creators to discover open leads and pitch quotes.
    """

    # The business profile seeking creators
    business = models.ForeignKey(
        'businesses.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='requirements',
        help_text="The brand seeking creator collaborations."
    )

    # Requirement headline title
    title = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Headline title of the open requirement."
    )

    # Domain category vertical
    category = models.ForeignKey(
        'taxonomies.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
        help_text="Taxonomy domain category vertical."
    )

    # Descriptive location string (e.g. 'Worldwide Remote', 'Dubai, UAE')
    location_text = models.CharField(
        max_length=150,
        blank=True,
        help_text="Descriptive location summary for requirement cards."
    )

    # Geographic location node for filtering
    location = models.ForeignKey(
        'taxonomies.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requirements',
        help_text="Geographic city/country node."
    )

    # Minimum budget guidance in smallest currency unit (paise/cents)
    min_budget_cents = models.PositiveIntegerField(
        default=0,
        help_text="Minimum estimated compensation budget in smallest currency unit."
    )

    # Maximum budget guidance in smallest currency unit (paise/cents)
    max_budget_cents = models.PositiveIntegerField(
        default=0,
        help_text="Maximum estimated compensation budget in smallest currency unit."
    )

    # Three-letter currency code (ISO 4217)
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code."
    )

    # Number of creators needed
    creators_needed = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of creators needed for this requirement."
    )

    # Total applications submitted
    applications_count = models.PositiveIntegerField(
        default=0,
        help_text="Total pitches submitted to this requirement."
    )

    # Moderation and publication status
    status = models.CharField(
        max_length=20,
        choices=RequirementStatus.choices,
        default=RequirementStatus.OPEN,
        db_index=True,
        help_text="Status on the public requirement board."
    )

    # Scope of work description
    description = models.TextField(
        blank=True,
        help_text="Detailed project requirements, style guidelines, and expectations."
    )

    class Meta:
        verbose_name = 'Requirement'
        verbose_name_plural = 'Requirements'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of requirement.
        
        :return: Requirement title and business.
        """
        return f"{self.title} ({self.business.company_name})"


class BidStatus(models.TextChoices):
    """Evaluation status of a creator's proposal pitch."""
    PENDING = 'PENDING', 'Pending Review'
    SHORTLISTED = 'SHORTLISTED', 'Shortlisted'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    REJECTED = 'REJECTED', 'Rejected'


class CampaignBid(BaseModel):
    """
    Formal pitch and commercial bid submitted by a creator for a Campaign or Requirement.
    
    Enforces that a creator submits at most one proposal per campaign.
    """

    # Target campaign being pitched for
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='bids',
        help_text="The campaign opportunity being applied for."
    )

    # The pitching creator profile
    creator = models.ForeignKey(
        'creators.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='campaign_bids',
        help_text="The creator submitting this application."
    )

    # Optional origin requirement if this pitch converted from an open requirement board
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bids',
        help_text="Associated requirement if originated from the public lead board."
    )

    # Narrative pitch explaining the creator's creative concept and vision
    pitch = models.TextField(
        help_text="Creator's application cover letter and creative proposal."
    )

    # Proposed quotation fee in smallest currency unit (paise/cents)
    proposed_fee_cents = models.PositiveIntegerField(
        default=0,
        help_text="Proposed quote fee in smallest currency denomination."
    )

    # Three-letter currency code (ISO 4217)
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code for the bid."
    )

    # Status of the bid in the brand review pipeline
    status = models.CharField(
        max_length=20,
        choices=BidStatus.choices,
        default=BidStatus.PENDING,
        db_index=True,
        help_text="Review decision status (pending, shortlisted, accepted, rejected)."
    )

    # Algorithmic match percentage based on category and location overlap (0-100)
    match_percentage = models.PositiveSmallIntegerField(
        default=0,
        help_text="Calculated match score percentage between creator and brief."
    )

    class Meta:
        verbose_name = 'Campaign Bid'
        verbose_name_plural = 'Campaign Bids'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['campaign', 'creator'], name='campaign_creator_bid_uniq')
        ]

    def __str__(self) -> str:
        """
        String representation of bid.
        
        :return: Creator handle and campaign title.
        """
        return f"Bid: @{self.creator.handle} -> {self.campaign.title} ({self.status})"


class InquiryStatus(models.TextChoices):
    """Conversation negotiation status for direct brand inquiries."""
    NEW = 'NEW', 'New Inquiry'
    RESPONDED = 'RESPONDED', 'Responded'
    NEGOTIATING = 'NEGOTIATING', 'Negotiating'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    DECLINED = 'DECLINED', 'Declined'


class Inquiry(BaseModel):
    """
    Direct brand-to-creator collaboration inquiry thread.
    
    Enables brand representatives to initiate private negotiations, discuss briefs,
    and exchange deliverables before formal campaign contracting.
    """

    # Originating brand profile
    business = models.ForeignKey(
        'businesses.BusinessProfile',
        on_delete=models.CASCADE,
        related_name='inquiries_sent',
        help_text="The business account initiating this direct conversation."
    )

    # Target creator profile
    creator = models.ForeignKey(
        'creators.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='inquiries_received',
        help_text="The creator receiving this collaboration proposal."
    )

    # Optional campaign link if conversation discusses an existing campaign
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inquiries',
        help_text="Associated campaign brief if relevant."
    )

    # Conversation subject line (e.g. 'Winter Resort Showcase Collaboration')
    subject = models.CharField(
        max_length=200,
        help_text="Headline subject of this collaboration thread."
    )

    # Proposed initial budget in smallest currency unit (paise/cents)
    budget_cents = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Initial budget indication in smallest currency unit."
    )

    # Three-letter currency code (ISO 4217)
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="Three-letter ISO 4217 currency code."
    )

    # Lifecycle status of the inquiry negotiation
    status = models.CharField(
        max_length=20,
        choices=InquiryStatus.choices,
        default=InquiryStatus.NEW,
        db_index=True,
        help_text="Negotiation progress state (new, responded, negotiating, accepted, declined)."
    )

    class Meta:
        verbose_name = 'Inquiry'
        verbose_name_plural = 'Inquiries'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of inquiry.
        
        :return: Brand, creator, and subject.
        """
        return f"Inquiry: {self.business.company_name} -> @{self.creator.handle} [{self.subject}]"


class InquiryMessage(BaseModel):
    """
    Individual chronological message within a brand-to-creator Inquiry thread.
    """

    # Parent inquiry conversation thread
    inquiry = models.ForeignKey(
        Inquiry,
        on_delete=models.CASCADE,
        related_name='messages',
        help_text="The parent inquiry thread to which this message belongs."
    )

    # The user account (brand manager or creator) who authored the message
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_inquiry_messages',
        help_text="The authenticated user authoring this message."
    )

    # Message textual content body
    body = models.TextField(
        help_text="Textual message content."
    )

    # Optional CDN URL pointing to an attached brief PDF, rate sheet, or storyboard
    attachment_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="CDN URL pointing to an attached media or document asset."
    )

    # Read receipt flag indicating whether the counterparty has opened this message
    is_read = models.BooleanField(
        default=False,
        help_text="True if the recipient has opened and read this message."
    )

    class Meta:
        verbose_name = 'Inquiry Message'
        verbose_name_plural = 'Inquiry Messages'
        ordering = ['created_at']

    def __str__(self) -> str:
        """
        String representation of message.
        
        :return: Sender email and preview.
        """
        return f"Message from {self.sender.email} on {self.inquiry.subject}"
