from django.db import models
from django.utils.text import slugify

from apps.common.models import BaseModel


class Category(BaseModel):
    """
    Taxonomy classification category for creators, campaigns, and marketplace discovery.
    
    Used to organize creators into verticals (e.g. Travel, Fashion, Food, Tech)
    and enables businesses to discover influencers by domain niche.
    """

    # Human-readable title of the category (e.g. 'Travel & Lifestyle', 'Fashion & Beauty')
    name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Unique title of the discovery category."
    )

    # URL-friendly slug used for routing and API filtering
    slug = models.SlugField(
        max_length=120,
        unique=True,
        db_index=True,
        help_text="URL-safe unique identifier automatically derived from the category title."
    )

    # Numerical sorting position for explicit display ordering in navigation menus and dropdowns
    order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Display order index (lower values appear first)."
    )

    # Administrative visibility toggle enabling or disabling this category across frontends
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this category is active and visible in filters."
    )

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self) -> str:
        """
        String representation of the category.
        
        :return: Category name.
        """
        return self.name

    def save(self, *args, **kwargs) -> None:
        """
        Override save to automatically generate a unique slug if not explicitly provided.
        
        :param args: Variable positional arguments for Model.save.
        :param kwargs: Variable keyword arguments for Model.save.
        :return: None
        :raises django.db.DatabaseError: If database persistence fails during save.
        """
        # Step 1: Auto-generate slug from name if missing
        if not self.slug:
            self.slug = slugify(self.name)

        # Step 2: Delegate to standard model save
        super().save(*args, **kwargs)


class LocationType(models.TextChoices):
    """
    Granular hierarchical location classification levels.
    Supports global multi-country representation with flexible depth.
    """
    COUNTRY = 'COUNTRY', 'Country'
    REGION = 'REGION', 'Region / State / Province'
    DISTRICT = 'DISTRICT', 'District / County'
    CITY = 'CITY', 'City'
    AREA = 'AREA', 'Area / Neighborhood'


class Location(BaseModel):
    """
    Hierarchical global geographic location node.
    
    Powers location autocomplete, radius-based opportunity matching,
    and marketplace geographic filters from country down to area level.
    """

    # Official title of the geographic place (e.g. 'United Arab Emirates', 'Dubai', 'Downtown')
    name = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Standard name of this geographic entity."
    )

    # Hierarchical tier level classifying this geographic entity
    type = models.CharField(
        max_length=20,
        choices=LocationType.choices,
        db_index=True,
        help_text="Hierarchical tier (Country, Region, District, City, Area)."
    )

    # Self-referencing foreign key pointing to the immediate enclosing parent location
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Enclosing parent location node (null for top-level countries)."
    )

    # Two-letter ISO 3166-1 alpha-2 country code (e.g. 'IN', 'AE', 'US')
    country_code = models.CharField(
        max_length=2,
        blank=True,
        db_index=True,
        help_text="Two-letter ISO 3166-1 alpha-2 country code."
    )

    # Geographic coordinate latitude in decimal degrees
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="WGS-84 latitude coordinate in decimal degrees."
    )

    # Geographic coordinate longitude in decimal degrees
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="WGS-84 longitude coordinate in decimal degrees."
    )

    # Administrative toggle enabling or disabling this location from active search index
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Designates whether this location is active in search and discovery."
    )

    class Meta:
        verbose_name = 'Location'
        verbose_name_plural = 'Locations'
        indexes = [
            models.Index(fields=['parent', 'type'], name='loc_parent_type_idx'),
        ]
        ordering = ['name']

    def __str__(self) -> str:
        """
        String representation showing place name and location type.
        
        :return: Formatted place description.
        """
        if self.parent:
            return f"{self.name} ({self.get_type_display()}, {self.parent.name})"
        return f"{self.name} ({self.get_type_display()})"

    def get_full_path(self) -> str:
        """
        Recursively compile the full hierarchical path string from root country down to this node.
        
        Example output: "India > Kerala > Ernakulam > Kochi"
        
        :return: Greater-than-delimited path of ancestors.
        """
        # Step 1: Base case if parent is root
        if not self.parent:
            return self.name

        # Step 2: Recursively prepend parent path
        return f"{self.parent.get_full_path()} > {self.name}"

    @property
    def full_path(self) -> str:
        """Convenience property alias for get_full_path."""
        return self.get_full_path()
