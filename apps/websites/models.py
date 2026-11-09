from django.db import models
from django.utils.text import slugify

from apps.common.models import BaseModel


class WebsiteStatus(models.TextChoices):
    """Lifecycle and deployment status of a hosted creator website."""
    DRAFT = 'DRAFT', 'Draft'
    PUBLISHED = 'PUBLISHED', 'Published'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    DOMAIN_PENDING = 'DOMAIN_PENDING', 'Custom Domain Pending'
    DOMAIN_CONNECTED = 'DOMAIN_CONNECTED', 'Custom Domain Connected'


class WebsiteTemplate(models.TextChoices):
    """Available curated frontend website templates."""
    MINIMAL = 'MINIMAL', 'Minimal Clean'
    FASHION = 'FASHION', 'Fashion Editorial'
    TRAVEL = 'TRAVEL', 'Travel & Culture'
    MAGAZINE = 'MAGAZINE', 'Magazine Showcase'
    MODERN_AGENCY = 'MODERN_AGENCY', 'Modern Agency'


class CreatorWebsite(BaseModel):
    """
    Dedicated influencer website hosted on the Influencers.com platform.
    
    Acts as the creator's digital home on the web, aggregating their verified bio,
    portfolio showcases, rate card services, and social audience metrics.
    Maintains a 1:1 relationship with CreatorProfile.
    """

    # Link to the owner creator profile
    creator = models.OneToOneField(
        'creators.CreatorProfile',
        on_delete=models.CASCADE,
        related_name='website',
        help_text="The creator profile owning this personal website."
    )

    # Selected visual design theme template
    template = models.CharField(
        max_length=50,
        choices=WebsiteTemplate.choices,
        default=WebsiteTemplate.MINIMAL,
        help_text="Visual layout and theme template."
    )

    # Public headline title displayed in site navigation header
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Site title or creator brand header (e.g. 'Ananya Nair')."
    )

    # Hero tagline displayed in the main splash banner
    tagline = models.CharField(
        max_length=255,
        blank=True,
        help_text="Catchphrase or sub-heading (e.g. 'Stories rooted in place')."
    )

    # Unique subdomain prefix on the platform's multi-tenant wild-card host (e.g. ananya.influencers.site)
    subdomain = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique subdomain slug prefix hosted at <subdomain>.influencers.site."
    )

    # Primary brand accent color in hex code format (e.g. '#6366f1')
    accent_color = models.CharField(
        max_length=30,
        default='#6366f1',
        help_text="Hex color code used for buttons, badges, and link accents."
    )

    # Primary typography font family name (e.g. 'Inter', 'Outfit', 'Playfair Display')
    font_family = models.CharField(
        max_length=50,
        default='Inter',
        help_text="Primary font family applied to headings and body text."
    )

    # General layout rhythm style (e.g. 'Standard', 'Editorial', 'Gallery', 'Story')
    layout_style = models.CharField(
        max_length=50,
        default='Standard',
        help_text="Structural layout arrangement and grid rhythm style."
    )

    # Operational lifecycle state (draft, published, domain pending, etc.)
    status = models.CharField(
        max_length=30,
        choices=WebsiteStatus.choices,
        default=WebsiteStatus.DRAFT,
        db_index=True,
        help_text="Publishing and domain deployment status."
    )

    # Public visibility toggle
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if the website is live and publicly accessible."
    )

    # Timestamp when the site debuted live
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of initial or latest site publication."
    )

    # Optional URL to an external pre-existing creator website if not using hosted builder
    external_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="External website URL if creator links an existing external domain."
    )

    # Aggregated visitor traffic counter over rolling 30-day window
    visitors_count = models.PositiveIntegerField(
        default=0,
        help_text="Rolling 30-day unique visitor page view counter."
    )

    class Meta:
        verbose_name = 'Creator Website'
        verbose_name_plural = 'Creator Websites'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of website.
        
        :return: Subdomain and creator handle.
        """
        return f"{self.subdomain}.influencers.site (@{self.creator.handle})"

    def save(self, *args, **kwargs) -> None:
        """
        Auto-populate subdomain from creator handle if empty.
        
        :param args: Variable positional arguments for Model.save.
        :param kwargs: Variable keyword arguments for Model.save.
        :return: None
        """
        if not self.subdomain and hasattr(self, 'creator') and self.creator:
            self.subdomain = slugify(self.creator.handle.replace('.', '-'))
        super().save(*args, **kwargs)


class WebsiteSection(BaseModel):
    """
    Modular block component configured on a creator's website.
    
    Controls visibility, ordering, and JSON configuration for modular sections
    (e.g., 'Hero', 'About', 'Social Media', 'Portfolio', 'Services', 'Collaborations', 'Contact').
    """

    # Parent website containing this section
    website = models.ForeignKey(
        CreatorWebsite,
        on_delete=models.CASCADE,
        related_name='sections',
        help_text="The parent website containing this section."
    )

    # Section identifier title (e.g. 'Hero', 'About', 'Portfolio', 'Services', 'Contact')
    section_name = models.CharField(
        max_length=50,
        help_text="Functional section block name (e.g. 'About', 'Portfolio', 'Services')."
    )

    # Active display toggle
    is_enabled = models.BooleanField(
        default=True,
        help_text="Designates whether this section is displayed on the public site."
    )

    # Vertical render order rank on page
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order index (lower indices appear higher up on page)."
    )

    # Section-specific parameters, copy overrides, or layout toggles
    config_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="Section configuration payload (custom headlines, filter IDs, etc.)."
    )

    class Meta:
        verbose_name = 'Website Section'
        verbose_name_plural = 'Website Sections'
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['website', 'section_name'], name='website_section_uniq')
        ]

    def __str__(self) -> str:
        """
        String representation of website section.
        
        :return: Section name and website subdomain.
        """
        return f"{self.section_name} ({self.website.subdomain})"


class DomainType(models.TextChoices):
    """Classification of creator site domain records."""
    CUSTOM = 'CUSTOM', 'Custom Domain'
    SUBDOMAIN = 'SUBDOMAIN', 'Subdomain'


class DomainVerificationStatus(models.TextChoices):
    """DNS validation status for apex/custom domains."""
    PENDING = 'PENDING', 'Pending Verification'
    VERIFIED = 'VERIFIED', 'Verified'
    FAILED = 'FAILED', 'Verification Failed'


class DomainSSLStatus(models.TextChoices):
    """Automated SSL/TLS certificate provisioning status."""
    ACTIVE = 'ACTIVE', 'SSL Active'
    PENDING = 'PENDING', 'SSL Pending'
    FAILED = 'FAILED', 'SSL Failed'


class DomainRecord(BaseModel):
    """
    Custom apex domain or subdomain mapped to a CreatorWebsite.
    
    Tracks DNS TXT verification token, A-record and CNAME validation,
    and Let's Encrypt / automated SSL certificate status.
    """

    # Target website mapped to this domain
    website = models.ForeignKey(
        CreatorWebsite,
        on_delete=models.CASCADE,
        related_name='domain_records',
        help_text="The creator website bound to this domain."
    )

    # Full Fully Qualified Domain Name (FQDN) e.g. 'ananyanair.com'
    domain = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Fully qualified custom domain name (e.g. 'ananyanair.com')."
    )

    # Domain classification (custom apex domain vs platform subdomain)
    domain_type = models.CharField(
        max_length=20,
        choices=DomainType.choices,
        default=DomainType.CUSTOM,
        help_text="Classification type of domain mapping."
    )

    # DNS validation status
    verification_status = models.CharField(
        max_length=20,
        choices=DomainVerificationStatus.choices,
        default=DomainVerificationStatus.PENDING,
        db_index=True,
        help_text="Ownership validation status via DNS records."
    )

    # SSL certificate issuance status
    ssl_status = models.CharField(
        max_length=20,
        choices=DomainSSLStatus.choices,
        default=DomainSSLStatus.PENDING,
        db_index=True,
        help_text="TLS/SSL certificate provisioning status."
    )

    # Unique unguessable challenge token required in DNS TXT record
    dns_txt_token = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique challenge token required in _influencers TXT record (e.g. 'verify=dom-401')."
    )

    # Timestamp of the most recent DNS probe
    last_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent automated DNS check."
    )

    # Timestamp when DNS ownership and SSL certificate successfully cleared
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when DNS and SSL verification succeeded."
    )

    class Meta:
        verbose_name = 'Domain Record'
        verbose_name_plural = 'Domain Records'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of domain mapping.
        
        :return: Domain name and verification status.
        """
        return f"{self.domain} [{self.verification_status}]"
