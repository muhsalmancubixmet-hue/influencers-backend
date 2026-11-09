import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


class UserRole(models.TextChoices):
    """Enumeration of user tenancy roles across the multi-portal platform."""
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    STAFF = 'STAFF', 'Staff Member'
    CREATOR = 'CREATOR', 'Creator / Influencer'
    BUSINESS = 'BUSINESS', 'Business / Brand'


class AccessLevel(models.TextChoices):
    """
    Standard 6-tier RBAC access clearance hierarchy.
    Integer weights: FULL(6) > MANAGE(5) > MODERATE(4) > VIEW(3) > LIMITED(2) > NONE(1).
    """
    FULL = 'FULL', 'Full Access (Tier 6)'
    MANAGE = 'MANAGE', 'Manage (Tier 5)'
    MODERATE = 'MODERATE', 'Moderate (Tier 4)'
    VIEW = 'VIEW', 'View Only (Tier 3)'
    LIMITED = 'LIMITED', 'Limited Access (Tier 2)'
    NONE = 'NONE', 'No Access (Tier 1)'


ACCESS_TIER_WEIGHTS = {
    AccessLevel.FULL: 6,
    AccessLevel.MANAGE: 5,
    AccessLevel.MODERATE: 4,
    AccessLevel.VIEW: 3,
    AccessLevel.LIMITED: 2,
    AccessLevel.NONE: 1,
}


class ModuleChoice(models.TextChoices):
    """The 14 operational system modules governed by role permission matrices."""
    INFLUENCERS = 'influencers', 'Influencers & Creators'
    BUSINESSES = 'businesses', 'Businesses & Brands'
    CAMPAIGNS = 'campaigns', 'Marketplace Campaigns'
    REQUIREMENTS = 'requirements', 'Marketplace Requirements'
    WEBSITES = 'websites', 'Creator Websites'
    DOMAINS = 'domains', 'Custom Domains & DNS'
    SOCIAL_PLATFORMS = 'social_platforms', 'Social Platforms & APIs'
    PAYMENTS = 'payments', 'Payments & Transactions'
    SUBSCRIPTIONS = 'subscriptions', 'Subscription Plans & Billing'
    SUPPORT = 'support', 'Support Tickets & Console'
    AUDIT_LOGS = 'audit_logs', 'System Audit Trail'
    SETTINGS = 'settings', 'Platform Settings'
    TAXONOMIES = 'taxonomies', 'Taxonomies (Categories & Locations)'
    MEDIA = 'media', 'Media Library & CDN'


class User(AbstractUser, BaseModel):
    """
    Custom user model for the SaaS platform.
    
    Substitutes standard Django integer primary key with UUIDv4 and enforces
    unique email-based authentication across all tenant portals (Admin, Creator, Brand).
    """

    # Non-sequential UUID primary key overriding AbstractUser default auto-increment ID
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Globally unique UUID identifier for the user account."
    )

    # Primary electronic mail address used as the unique credential for sign-in
    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="Unique corporate or personal email address used for login."
    )

    # Tenant portal role governing top-level boundary (Staff/Admin vs Creator vs Business)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CREATOR,
        db_index=True,
        help_text="Top-level security boundary classifying the user's operational portal."
    )

    # Optional contact telephone number including international dialing prefix
    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Contact telephone number with country calling code."
    )

    # Multi-factor authentication flag indicating mandatory TOTP / OTP verification
    mfa_enabled = models.BooleanField(
        default=False,
        help_text="Designates whether two-factor authentication is active on this account."
    )

    # Configure email as the primary login credential
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        Human-readable representation of user instance.
        
        :return: Formatted string containing email and role tag.
        """
        return f"{self.email} ({self.role})"


class RoleTemplate(BaseModel):
    """
    Predefined or custom administrative role archetype (e.g., Super Admin, Moderator).
    
    Represents a named collection of module permissions that can be assigned
    to staff members. System roles are protected against deletion.
    """

    # Unique name of the administrative role template
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique administrative role title (e.g. 'Moderator', 'Finance')."
    )

    # Comprehensive human-readable summary of responsibilities under this role
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the responsibilities and scope of this role template."
    )

    # System protection flag preventing default seeded roles from being deleted
    is_system_role = models.BooleanField(
        default=False,
        help_text="True if this is a built-in immutable system role that cannot be deleted."
    )

    class Meta:
        verbose_name = 'Role Template'
        verbose_name_plural = 'Role Templates'
        ordering = ['name']

    def __str__(self) -> str:
        """
        String representation of the role template.
        
        :return: Role template name.
        """
        return self.name


class RolePermission(BaseModel):
    """
    Granular permission rule granting an access tier to a role template for a specific module.
    
    Maps a RoleTemplate to one of the 14 operational modules with an explicit AccessLevel.
    """

    # Reference to the parent role template possessing this clearance
    role_template = models.ForeignKey(
        RoleTemplate,
        on_delete=models.CASCADE,
        related_name='permissions',
        help_text="The role template to which this module permission rule belongs."
    )

    # The operational system domain governed by this clearance rule
    module = models.CharField(
        max_length=50,
        choices=ModuleChoice.choices,
        help_text="The specific operational module being governed."
    )

    # The maximum clearance level granted for this module
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.NONE,
        help_text="The access clearance tier (FULL, MANAGE, MODERATE, VIEW, LIMITED, NONE)."
    )

    class Meta:
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
        unique_together = ('role_template', 'module')
        ordering = ['role_template', 'module']

    def __str__(self) -> str:
        """
        String representation of module clearance rule.
        
        :return: Formatted description of role, module, and tier.
        """
        return f"{self.role_template.name} -> {self.module}: {self.access_level}"

    @property
    def weight(self) -> int:
        """
        Return the integer ranking weight of this clearance level.
        
        :return: Integer weight from 1 (NONE) to 6 (FULL).
        """
        return ACCESS_TIER_WEIGHTS.get(self.access_level, 0)


class StaffProfile(BaseModel):
    """
    Administrative profile linked one-to-one with a User record possessing the STAFF role.
    
    Holds active status, assigned role template, and activity tracking for SaaS managers.
    """

    # One-to-one relationship linking administrative attributes to the core User identity
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='staff_profile',
        help_text="The core User account associated with this staff administration profile."
    )

    # The assigned role template governing the staff member's operational matrix
    role_template = models.ForeignKey(
        RoleTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_staff',
        help_text="Assigned role template dictating granular module permissions."
    )

    # Administrative toggle enabling or locking console access for this staff member
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this staff member currently has active admin access."
    )

    # Timestamp of the staff member's most recent action inside the control panel
    last_active_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the staff member's most recent administrative action."
    )

    class Meta:
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of staff profile.
        
        :return: Staff user email and role template.
        """
        role_name = self.role_template.name if self.role_template else "Unassigned"
        return f"Staff: {self.user.email} [{role_name}]"


class StaffInvitation(BaseModel):
    """
    Pending administrative invitation issued by a Super Admin to onboard a new staff member.
    
    Contains an unguessable UUID token sent via email, an expiration timestamp,
    and the pre-assigned role template.
    """

    # Corporate email address designated to receive the staff onboarding invitation
    email = models.EmailField(
        db_index=True,
        help_text="Target corporate email address invited to the admin console."
    )

    # Pre-configured role template that will be granted upon accepting the invite
    role_template = models.ForeignKey(
        RoleTemplate,
        on_delete=models.CASCADE,
        related_name='invitations',
        help_text="Role template to assign upon successful invite acceptance."
    )

    # Secure single-use invitation token validated during onboarding
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Unguessable UUID token passed in the invitation acceptance URL."
    )

    # The administrative user who authorized and dispatched this invitation
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_staff_invitations',
        help_text="Super Admin or Staff member who generated this invitation."
    )

    # Expiration timestamp after which the invitation token is no longer redeemable
    expires_at = models.DateTimeField(
        help_text="Timestamp when this onboarding invitation expires."
    )

    # Boolean flag indicating whether the invite has already been redeemed
    is_accepted = models.BooleanField(
        default=False,
        help_text="True if this invitation has already been accepted and redeemed."
    )

    class Meta:
        verbose_name = 'Staff Invitation'
        verbose_name_plural = 'Staff Invitations'
        ordering = ['-created_at']

    def __str__(self) -> str:
        """
        String representation of staff invitation.
        
        :return: Target email and assigned role.
        """
        return f"Invite: {self.email} -> {self.role_template.name}"

    def is_expired(self) -> bool:
        """
        Determine if the invitation token has exceeded its validity window.
        
        :return: True if current UTC time exceeds expires_at timestamp, False otherwise.
        """
        return timezone.now() > self.expires_at