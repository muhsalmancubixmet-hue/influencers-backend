from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class BusinessVerificationStatus(models.TextChoices):
    """Lifecycle status choices for business identity and tax verification."""
    UNVERIFIED = 'UNVERIFIED', 'Unverified'
    PENDING = 'PENDING', 'Pending Verification'
    VERIFIED = 'VERIFIED', 'Verified'
    REJECTED = 'REJECTED', 'Verification Rejected'


class BusinessStatus(models.TextChoices):
    """Operational status of the business account."""
    ACTIVE = 'ACTIVE', 'Active'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    PENDING = 'PENDING', 'Pending Review'


class BusinessProfile(BaseModel):
    """
    Brand and business workspace profile.
    
    Represents corporate brand entities that fund campaigns, post creator requirements,
    and hire influencers across the marketplace. Holds corporate contact and tax credentials.
    """

    # Link to the underlying user account possessing the BUSINESS tenant role
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='business_profile',
        help_text="The core user identity possessing the BUSINESS tenant role."
    )

    # Registered legal or commercial business trade name
    company_name = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Commercial trade name of the brand or company."
    )

    # Industry classification sector (e.g. 'Hospitality & Dining', 'Fashion & Retail', 'Tech')
    business_type = models.CharField(
        max_length=100,
        help_text="Commercial vertical or industry domain classification."
    )

    # Global headquarters geographic location node
    hq_location = models.ForeignKey(
        'taxonomies.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='businesses_hq',
        help_text="Primary geographic headquarters city/country."
    )

    # Name of primary corporate representative or marketing manager
    contact_name = models.CharField(
        max_length=150,
        help_text="Full name of primary brand representative or campaign manager."
    )

    # Corporate communication email address
    contact_email = models.EmailField(
        help_text="Official email address for campaign proposals and invoicing."
    )

    # Direct phone contact number including country calling code
    contact_phone = models.CharField(
        max_length=30,
        blank=True,
        help_text="Direct telephone contact number for brand representative."
    )

    # Narrative describing brand story, products, and target audience
    about = models.TextField(
        blank=True,
        help_text="Detailed company background and marketing objectives."
    )

    # Brand trademark logo image URL served from CDN
    logo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="CDN URL pointing to official company trademark logo."
    )

    # Corporate tax registration identifier (e.g. GSTIN, PAN, VAT, EIN)
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Corporate tax identification number (GSTIN, VAT, or EIN)."
    )

    # Official business verification status
    verification_status = models.CharField(
        max_length=20,
        choices=BusinessVerificationStatus.choices,
        default=BusinessVerificationStatus.UNVERIFIED,
        db_index=True,
        help_text="Current identity verification status evaluated by staff."
    )

    # Operational lifecycle status (active, suspended, pending)
    status = models.CharField(
        max_length=20,
        choices=BusinessStatus.choices,
        default=BusinessStatus.ACTIVE,
        db_index=True,
        help_text="Operational lifecycle state dictating marketplace permissions."
    )

    # Key-value mapping of business notification preference toggles
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Key-value mapping of business notification preference toggles."
    )

    class Meta:
        verbose_name = 'Business Profile'
        verbose_name_plural = 'Business Profiles'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of business profile.
        
        :return: Company trade name.
        """
        return self.company_name


class BusinessOperatingLocation(BaseModel):
    """
    Physical branch, franchise, or operational market location for a business.
    
    Allows businesses with multiple venues (e.g. restaurant chains, resort groups)
    to target local creators within specific geographic radii.
    """

    # Target business profile owning this operating branch
    business = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        related_name='operating_locations',
        help_text="The parent business entity operating this branch."
    )

    # Descriptive branch label (e.g. 'Flagship Store', 'Kochi Seafront Outlet')
    label = models.CharField(
        max_length=100,
        help_text="Branch or outlet identifier (e.g. 'Kochi Marina Branch')."
    )

    # Street level physical address
    address = models.CharField(
        max_length=255,
        help_text="Street-level physical address of this outlet."
    )

    # Underlying geographic taxonomy location node
    location = models.ForeignKey(
        'taxonomies.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='business_operating_areas',
        help_text="Geographic city or district where this venue operates."
    )

    # Geographic campaign target radius in kilometers from this location
    radius_km = models.PositiveIntegerField(
        default=25,
        help_text="Operational targeting radius in kilometers surrounding this venue."
    )

    class Meta:
        verbose_name = 'Business Operating Location'
        verbose_name_plural = 'Business Operating Locations'
        ordering = ['label']

    def __str__(self) -> str:
        """
        String representation of operating branch.
        
        :return: Label and parent business.
        """
        return f"{self.business.company_name} - {self.label}"


class BusinessShortlist(BaseModel):
    """
    Curated shortlist folder managed by a brand to organize target creators.
    
    Powers campaign outreach lists, talent rosters, and saved creator collections.
    """
    business = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        related_name='shortlists',
        help_text="Brand entity owning this shortlist."
    )
    name = models.CharField(
        max_length=150,
        help_text="Shortlist display name (e.g. 'Kerala Travel Creators', 'Diwali Reel Roster')."
    )
    description = models.TextField(
        blank=True,
        help_text="Optional notes or campaign goal description for this shortlist."
    )
    color = models.CharField(
        max_length=30,
        default='emerald',
        help_text="Color tag / theme identifier for UI card visualization."
    )
    is_archived = models.BooleanField(
        default=False,
        help_text="Archive flag hiding the shortlist from the primary workspace view."
    )

    class Meta:
        verbose_name = 'Business Shortlist'
        verbose_name_plural = 'Business Shortlists'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.business.company_name} - {self.name}"


class ShortlistEntry(BaseModel):
    """
    Relational association linking a Creator to a Brand's Shortlist.
    """
    shortlist = models.ForeignKey(
        BusinessShortlist,
        on_delete=models.CASCADE,
        related_name='entries',
        help_text="Enclosing shortlist folder."
    )
    creator = models.ForeignKey(
        'creators.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='shortlist_entries',
        help_text="Saved creator profile."
    )
    notes = models.TextField(
        blank=True,
        help_text="Private brand collaboration evaluation notes for this creator."
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Custom tags (e.g. ['High Engagement', 'Verified', 'Food Vertical'])."
    )

    class Meta:
        verbose_name = 'Shortlist Entry'
        verbose_name_plural = 'Shortlist Entries'
        unique_together = ('shortlist', 'creator')
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.shortlist.name} -> @{self.creator.handle}"


class BusinessSavedSearch(BaseModel):
    """
    Persisted creator discovery filter preset created by a business.

    Enables brand marketers to save complex multi-attribute search criteria
    (categories, locations, follower thresholds, budgets, languages) and toggle
    automated real-time notification alerts whenever new matching creators join.
    """

    # Enclosing business profile owning this search query
    business = models.ForeignKey(
        BusinessProfile,
        on_delete=models.CASCADE,
        related_name='saved_searches',
        help_text="Brand account that configured this saved search preset."
    )

    # User-facing title for this filter configuration
    name = models.CharField(
        max_length=200,
        db_index=True,
        help_text="User-defined descriptive name for this search configuration."
    )

    # Serialized filter criteria dictionary
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filter parameters dictionary (categories, locations, languages, platforms, follower range, budget, min_engagement)."
    )

    # Automated alert notification switch
    notify_enabled = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether to send notifications when new matching creators join."
    )

    # Number of new matching creators since last viewed
    new_matches_count = models.PositiveIntegerField(
        default=0,
        help_text="Counter for newly registered creators matching this search query."
    )

    class Meta:
        verbose_name = 'Business Saved Search'
        verbose_name_plural = 'Business Saved Searches'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of saved search.

        :return: Search name and business company name.
        """
        return f"{self.name} ({self.business.company_name})"


