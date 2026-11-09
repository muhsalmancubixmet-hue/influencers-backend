from rest_framework import serializers

# Core models and dependencies
from apps.creators.models import (
    CreatorProfile,
    CreatorCategory,
    CreatorLanguage,
    CreatorServiceArea,
    PortfolioItem,
    CreatorService,
    SocialAccount,
    VerificationStatus,
    ProfileStatus
)
from apps.taxonomies.api.v1.serializers import CategorySerializer, LocationSerializer


class CreatorCategorySerializer(serializers.ModelSerializer):
    """Serializer for creator category mapping with nested Category details."""
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)
    is_primary = serializers.BooleanField(default=False, read_only=True)

    class Meta:
        model = CreatorCategory
        fields = ['id', 'category', 'category_id', 'is_primary']


class CreatorLanguageSerializer(serializers.ModelSerializer):
    """Serializer for creator spoken/content languages."""

    class Meta:
        model = CreatorLanguage
        fields = ['id', 'language_code', 'language_name', 'proficiency']


class CreatorServiceAreaSerializer(serializers.ModelSerializer):
    """Serializer for creator regional operating radius."""
    location = LocationSerializer(read_only=True)
    location_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = CreatorServiceArea
        fields = ['id', 'location', 'location_id', 'radius_km']


class PortfolioItemSerializer(serializers.ModelSerializer):
    """Serializer for creator portfolio showcase projects."""
    image = serializers.URLField(source='media_url', required=False)
    brand = serializers.CharField(source='brand_name', required=False, allow_blank=True)
    format = serializers.CharField(source='format_tag', required=False, allow_blank=True)
    views = serializers.IntegerField(source='views_count', required=False)

    class Meta:
        model = PortfolioItem
        fields = [
            'id',
            'title',
            'description',
            'media_url',
            'media_type',
            'brand_name',
            'deliverable_date',
            'views_count',
            'format_tag',
            'order',
            'image',
            'brand',
            'format',
            'views',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CreatorServiceSerializer(serializers.ModelSerializer):
    """Serializer for creator bookable services and rate card packages."""
    service_type_name = serializers.CharField(source='service_type.name', read_only=True, allow_null=True)
    deliverables = serializers.CharField(source='deliverables_spec', required=False, allow_blank=True)
    price_cents = serializers.IntegerField(source='starting_price_cents', required=False)

    class Meta:
        model = CreatorService
        fields = [
            'id',
            'service_type',
            'service_type_name',
            'name',
            'description',
            'deliverables_spec',
            'deliverables',
            'turnaround_days',
            'starting_price_cents',
            'price_cents',
            'currency',
            'is_active',
            'is_contact_for_price',
            'created_at'
        ]
        read_only_fields = ['id', 'service_type_name', 'created_at']



class CreatorProfileSerializer(serializers.ModelSerializer):
    """Full creator profile serializer for Creator Workspace view."""
    email = serializers.EmailField(source='user.email', read_only=True)
    categories = CreatorCategorySerializer(many=True, read_only=True)
    languages = CreatorLanguageSerializer(many=True, read_only=True)
    service_areas = CreatorServiceAreaSerializer(many=True, read_only=True)
    primary_location_details = LocationSerializer(source='primary_location', read_only=True)
    current_location_details = LocationSerializer(source='current_location', read_only=True)
    mfa_enabled = serializers.BooleanField(source='user.mfa_enabled', read_only=True)
    preferences = serializers.JSONField(required=False)
    location_text = serializers.SerializerMethodField(read_only=True)

    def get_location_text(self, obj) -> str:
        """Compile a human-readable location string."""
        if obj.primary_location:
            loc = obj.primary_location
            parts = [loc.name]
            if loc.parent and loc.parent.name not in parts and loc.parent.name != "India":
                parts.append(loc.parent.name)
            if loc.country_code:
                parts.append("India" if loc.country_code == "IN" else loc.country_code)
            return ", ".join(parts)
        return ""

    def to_internal_value(self, data):
        """
        Custom deserialization resolving flexible string location inputs into relational Location ForeignKeys.
        Supports both direct UUIDs and free-text geographic strings (e.g. 'Nilambur, Kerala').
        """
        import uuid
        from apps.taxonomies.models import Location, LocationType

        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Support location_text or primary_location inputs
        loc_val = mutable_data.get('location_text') or mutable_data.get('primary_location')
        if loc_val is not None:
            if isinstance(loc_val, str):
                clean_loc = loc_val.strip()
                if clean_loc and clean_loc.lower() not in ("remote", "remote / worldwide", "none", ""):
                    is_uuid = False
                    try:
                        uuid.UUID(clean_loc)
                        is_uuid = True
                    except ValueError:
                        is_uuid = False

                    if not is_uuid:
                        parts = [p.strip() for p in clean_loc.split(',') if p.strip()]
                        primary_name = parts[0]
                        parent_hint = parts[1] if len(parts) > 1 else None

                        loc_obj = Location.objects.filter(name__iexact=primary_name, is_deleted=False).first()
                        if not loc_obj:
                            loc_obj = Location.objects.filter(name__icontains=primary_name, is_deleted=False).first()

                        if not loc_obj:
                            parent_node = None
                            if parent_hint:
                                parent_node = Location.objects.filter(name__iexact=parent_hint, is_deleted=False).first()
                            if not parent_node:
                                parent_node = Location.objects.filter(name__iexact="Kerala", is_deleted=False).first() or \
                                              Location.objects.filter(name__iexact="India", is_deleted=False).first()

                            loc_obj = Location.objects.create(
                                name=primary_name.title(),
                                type=LocationType.CITY,
                                parent=parent_node,
                                country_code="IN",
                                is_active=True
                            )

                        mutable_data['primary_location'] = str(loc_obj.id)
                elif clean_loc.lower() in ("remote", "remote / worldwide", ""):
                    mutable_data['primary_location'] = None
            elif loc_val is None:
                mutable_data['primary_location'] = None

        # Clean current_location similarly if provided
        curr_loc_val = mutable_data.get('current_location')
        if curr_loc_val and isinstance(curr_loc_val, str):
            clean_curr = curr_loc_val.strip()
            if clean_curr and clean_curr.lower() not in ("remote", "none", ""):
                try:
                    uuid.UUID(clean_curr)
                except ValueError:
                    parts = [p.strip() for p in clean_curr.split(',') if p.strip()]
                    first_p = parts[0]
                    curr_obj = Location.objects.filter(name__iexact=first_p, is_deleted=False).first()
                    if curr_obj:
                        mutable_data['current_location'] = str(curr_obj.id)
                    else:
                        mutable_data.pop('current_location', None)

        return super().to_internal_value(mutable_data)

    class Meta:
        model = CreatorProfile
        fields = [
            'id',
            'email',
            'handle',
            'display_name',
            'bio',
            'about',
            'photo_url',
            'cover_url',
            'primary_location',
            'primary_location_details',
            'location_text',
            'current_location',
            'current_location_details',
            'currency',
            'travel_available',
            'remote_available',
            'verification_status',
            'status',
            'completion_percentage',
            'preferences',
            'mfa_enabled',
            'categories',
            'languages',
            'service_areas',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'email',
            'verification_status',
            'status',
            'completion_percentage',
            'mfa_enabled',
            'created_at'
        ]


class AdminInfluencerListSerializer(serializers.ModelSerializer):
    """Tabular serializer for Control Panel influencer management table."""
    name = serializers.CharField(source='display_name', read_only=True)
    avatar = serializers.CharField(source='photo_url', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    primary_city = serializers.CharField(source='primary_location.name', read_only=True, allow_null=True)
    categories_list = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    followers = serializers.SerializerMethodField()
    platforms = serializers.SerializerMethodField()
    verification = serializers.SerializerMethodField()
    websiteStatus = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()

    class Meta:
        model = CreatorProfile
        fields = [
            'id',
            'name',
            'handle',
            'avatar',
            'bio',
            'email',
            'display_name',
            'photo_url',
            'primary_city',
            'categories',
            'categories_list',
            'location',
            'followers',
            'platforms',
            'verification',
            'verification_status',
            'websiteStatus',
            'status',
            'joined',
            'created_at'
        ]

    def get_categories(self, obj):
        return [c.category.name for c in obj.categories.select_related('category').all()]

    def get_categories_list(self, obj):
        return self.get_categories(obj)

    def get_location(self, obj):
        loc = obj.primary_location
        city = loc.name if loc else "Mumbai"
        country_code = loc.country_code if loc else "IN"
        lat = float(loc.latitude) if (loc and loc.latitude is not None) else 19.0760
        lng = float(loc.longitude) if (loc and loc.longitude is not None) else 72.8777
        country_name = "India" if country_code == "IN" else country_code
        return {
            "city": city,
            "district": "",
            "region": "",
            "country": country_name,
            "countryCode": country_code,
            "lat": lat,
            "lng": lng,
            "currency": "INR",
            "languages": ["English"],
        }

    def get_followers(self, obj):
        total = sum(acc.followers_count for acc in obj.social_accounts.all())
        return total

    def get_platforms(self, obj):
        names = [acc.platform.name for acc in obj.social_accounts.select_related('platform').all()]
        return names

    def get_verification(self, obj):
        return (obj.verification_status or "unverified").lower()

    def get_websiteStatus(self, obj):
        return "published" if hasattr(obj, 'website') and obj.website.is_published else "none"

    def get_joined(self, obj):
        return obj.created_at.strftime("%b %d, %Y") if obj.created_at else ""



class AdminInfluencerModerationSerializer(serializers.Serializer):
    """Payload contract for admin verification or status toggling."""
    verification_status = serializers.ChoiceField(choices=VerificationStatus.choices, required=False)
    status = serializers.ChoiceField(choices=ProfileStatus.choices, required=False)


class AdminInfluencerCreateSerializer(serializers.Serializer):
    """Payload contract for manually onboarding a creator by platform admin."""
    name = serializers.CharField(max_length=150)
    handle = serializers.CharField(max_length=80)
    email = serializers.EmailField()
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tier = serializers.CharField(max_length=50, required=False, default="Free")

    def validate_handle(self, value):
        clean_handle = value.strip().lstrip('@').lower()
        if not clean_handle:
            raise serializers.ValidationError("Handle cannot be empty.")
        if CreatorProfile.objects.filter(handle=clean_handle, is_deleted=False).exists():
            raise serializers.ValidationError("This handle is already taken.")
        return clean_handle

    def validate_email(self, value):
        clean_email = value.strip().lower()
        from apps.accounts.models import User
        if User.objects.filter(email=clean_email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return clean_email


class SocialAccountSerializer(serializers.ModelSerializer):
    """
    Serializer representing connected creator social media accounts.
    
    Exposes enriched platform branding and external channel audience metrics.
    """
    platform_name = serializers.CharField(source='platform.name', read_only=True)
    platform_slug = serializers.CharField(source='platform.slug', read_only=True)
    platform_icon = serializers.CharField(source='platform.icon_name', read_only=True)
    platform_color = serializers.CharField(source='platform.color_code', read_only=True)

    class Meta:
        model = SocialAccount
        fields = [
            'id',
            'platform',
            'platform_name',
            'platform_slug',
            'platform_icon',
            'platform_color',
            'username',
            'profile_url',
            'followers_count',
            'following_count',
            'engagement_rate',
            'is_verified',
            'last_synced_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'platform_name',
            'platform_slug',
            'platform_icon',
            'platform_color',
            'is_verified',
            'last_synced_at',
            'created_at',
            'updated_at'
        ]


class SocialAccountConnectSerializer(serializers.Serializer):
    """
    Payload contract for linking or updating a social network channel.
    
    Accepts platform identifier (UUID, slug, or name), username, and profile URL.
    """
    platform = serializers.CharField(
        max_length=100,
        help_text="Platform UUID, slug (e.g. 'instagram'), or name (e.g. 'Instagram')."
    )
    username = serializers.CharField(
        max_length=150,
        help_text="Username / handle on the external platform."
    )
    profile_url = serializers.URLField(
        max_length=2000,
        help_text="Direct public link to the creator's profile."
    )
    followers_count = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text="Claimed or initial follower count."
    )
    following_count = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text="Initial following count."
    )
    engagement_rate = serializers.DecimalField(
        required=False,
        default=0.0,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        help_text="Claimed or initial engagement percentage rate."
    )

    def validate_username(self, value: str) -> str:
        """
        Sanitize external platform username.
        
        :param value: Raw submitted handle.
        :return: Sanitized username stripped of leading @.
        :raises serializers.ValidationError: If handle is empty.
        """
        cleaned = value.strip().lstrip('@')
        if not cleaned:
            raise serializers.ValidationError("Username cannot be empty.")
        return cleaned


class AdminInfluencerDetailSerializer(serializers.ModelSerializer):
    """
    Comprehensive administrative detail serializer for Control Panel inspection.
    Nests social accounts, portfolio showcase, bookable services, website status,
    and recent activity events.
    """
    name = serializers.CharField(source='display_name', read_only=True)
    avatar = serializers.CharField(source='photo_url', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    categories = CreatorCategorySerializer(many=True, read_only=True)
    languages = CreatorLanguageSerializer(many=True, read_only=True)
    service_areas = CreatorServiceAreaSerializer(many=True, read_only=True)
    primary_location_details = LocationSerializer(source='primary_location', read_only=True)
    current_location_details = LocationSerializer(source='current_location', read_only=True)
    socials = serializers.SerializerMethodField()
    portfolio = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    website = serializers.SerializerMethodField()
    activity = serializers.SerializerMethodField()
    account = serializers.SerializerMethodField()

    class Meta:
        model = CreatorProfile
        fields = [
            'id',
            'name',
            'email',
            'handle',
            'display_name',
            'avatar',
            'bio',
            'about',
            'photo_url',
            'cover_url',
            'primary_location',
            'primary_location_details',
            'location_text',
            'current_location',
            'current_location_details',
            'currency',
            'travel_available',
            'remote_available',
            'verification_status',
            'status',
            'completion_percentage',
            'preferences',
            'categories',
            'languages',
            'service_areas',
            'socials',
            'portfolio',
            'services',
            'website',
            'activity',
            'account',
            'created_at'
        ]

    def get_socials(self, obj):
        accs = obj.social_accounts.filter(is_deleted=False)
        return SocialAccountSerializer(accs, many=True).data

    def get_portfolio(self, obj):
        items = obj.portfolio_items.filter(is_deleted=False).order_by('order', '-created_at')
        return PortfolioItemSerializer(items, many=True).data

    def get_services(self, obj):
        srvs = obj.services.filter(is_deleted=False).order_by('-created_at')
        return CreatorServiceSerializer(srvs, many=True).data

    def get_website(self, obj):
        from apps.websites.models import CreatorWebsite
        from apps.websites.api.v1.serializers import AdminWebsiteSerializer
        site = CreatorWebsite.objects.filter(creator=obj, is_deleted=False).first()
        if site:
            return AdminWebsiteSerializer(site).data
        return None

    def get_activity(self, obj):
        from apps.common.models import AuditLog
        from apps.common.api.v1.serializers import AuditLogSerializer
        logs = AuditLog.objects.filter(
            entity='CreatorProfile',
            entity_id=str(obj.id)
        ).order_by('-created_at')[:10]
        return AuditLogSerializer(logs, many=True).data

    def get_account(self, obj):
        u = obj.user
        return {
            'email': u.email,
            'is_active': u.is_active,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'created_at': obj.created_at.isoformat() if obj.created_at else None,
            'mfa_enabled': getattr(u, 'mfa_enabled', False),
            'role': u.role
        }


class PublicCreatorListSerializer(serializers.ModelSerializer):
    """
    Public discovery serializer for creator preview cards.
    
    Transforms internal normalized models into the public marketplace contract
    consumed by the discovery grid, search bar suggestions, and homepage showcase.
    """
    slug = serializers.CharField(source='handle', read_only=True)
    name = serializers.CharField(source='display_name', read_only=True)
    category = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    district = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    serviceLocations = serializers.SerializerMethodField()
    remote = serializers.BooleanField(source='remote_available', read_only=True)
    travels = serializers.BooleanField(source='travel_available', read_only=True)
    languages = serializers.SerializerMethodField()
    platforms = serializers.SerializerMethodField()
    followers = serializers.SerializerMethodField()
    followersLabel = serializers.SerializerMethodField()
    engagement = serializers.SerializerMethodField()
    verified = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()
    startingPrice = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()
    sprite = serializers.CharField(source='photo_url', read_only=True)
    position = serializers.SerializerMethodField()
    accent = serializers.SerializerMethodField()

    class Meta:
        model = CreatorProfile
        fields = [
            'id',
            'slug',
            'name',
            'handle',
            'category',
            'location',
            'city',
            'district',
            'country',
            'serviceLocations',
            'remote',
            'travels',
            'languages',
            'platforms',
            'followers',
            'followersLabel',
            'engagement',
            'bio',
            'verified',
            'available',
            'currency',
            'startingPrice',
            'photo_url',
            'sprite',
            'position',
            'accent',
            'joined'
        ]

    def get_category(self, obj) -> str:
        """Extract primary category name or fallback to first assigned vertical."""
        primary = obj.categories.first()
        return primary.category.name if primary and primary.category else "Creator"

    def get_location(self, obj):
        """
        Return structured geographic place dictionary for map markers and location filters.
        Provides a guaranteed non-null fallback place structure to prevent frontend runtime exceptions.
        """
        loc = obj.primary_location
        if not loc:
            return {
                'id': 'kerala',
                'city': obj.display_name and f"{obj.display_name}'s Location" or "Kerala",
                'district': "Kerala",
                'region': "Kerala",
                'country': "India",
                'countryCode': "IN",
                'lat': 10.8505,
                'lng': 76.2711
            }
        district_name = loc.parent.name if loc.parent else ""
        country_name = "India"
        if loc.country_code == "AE":
            country_name = "United Arab Emirates"
        elif loc.country_code == "GB":
            country_name = "United Kingdom"
        elif loc.country_code == "US":
            country_name = "United States"
        elif loc.country_code == "SG":
            country_name = "Singapore"
        elif loc.parent and loc.parent.type == 'COUNTRY':
            country_name = loc.parent.name
        elif loc.parent and loc.parent.parent and loc.parent.parent.type == 'COUNTRY':
            country_name = loc.parent.parent.name

        return {
            'id': str(loc.id),
            'city': loc.name,
            'district': district_name,
            'region': district_name,
            'country': country_name,
            'countryCode': loc.country_code or 'IN',
            'lat': float(loc.latitude) if loc.latitude is not None else 0.0,
            'lng': float(loc.longitude) if loc.longitude is not None else 0.0
        }

    def get_city(self, obj) -> str:
        """City of primary residence."""
        return obj.primary_location.name if obj.primary_location else ""

    def get_district(self, obj) -> str:
        """District or administrative province."""
        loc = obj.primary_location
        return loc.parent.name if loc and loc.parent else ""

    def get_country(self, obj) -> str:
        """Country of origin."""
        loc = obj.primary_location
        if not loc:
            return "India"
        if loc.country_code == "AE":
            return "United Arab Emirates"
        if loc.country_code == "GB":
            return "United Kingdom"
        if loc.country_code == "US":
            return "United States"
        if loc.country_code == "SG":
            return "Singapore"
        return "India"

    def get_serviceLocations(self, obj):
        """List of regional operating markets."""
        areas = [sa.location.name for sa in obj.service_areas.all() if sa.location]
        if not areas and obj.primary_location:
            areas = [obj.primary_location.name]
        return areas or ["Kerala", "Remote"]

    def get_languages(self, obj) -> list:
        """
        Active content and spoken languages declared by this creator.
        
        :param obj: CreatorProfile instance.
        :return: List of language display names, empty list if none specified.
        """
        # Step 1: Map language ISO codes to human-readable names
        lang_names = {
            'ml': 'Malayalam',
            'en': 'English',
            'hi': 'Hindi',
            'ar': 'Arabic',
            'ta': 'Tamil',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German'
        }
        langs = [lang_names.get(lang.language_code.lower(), lang.language_code.upper()) for lang in obj.languages.all()]
        return langs

    def get_platforms(self, obj) -> list:
        """
        Active social media platforms linked to this creator.
        
        :param obj: CreatorProfile instance.
        :return: List of active platform names, empty list if none connected.
        """
        # Step 1: Extract non-deleted connected platforms
        plats = [sa.platform.name for sa in obj.social_accounts.filter(is_deleted=False) if sa.platform]
        return plats

    def get_followers(self, obj) -> int:
        """
        Aggregate followers across all active connected social channels.
        
        :param obj: CreatorProfile instance.
        :return: Integer sum of followers, 0 if no social channels linked.
        """
        # Step 1: Compute total followers from active connected accounts
        total = sum(sa.followers_count or 0 for sa in obj.social_accounts.filter(is_deleted=False))
        return total

    def get_followersLabel(self, obj) -> str:
        """
        Human readable compact follower count (e.g. '0', '248K', '1.2M').
        
        :param obj: CreatorProfile instance.
        :return: Compact formatted follower string.
        """
        cnt = self.get_followers(obj)
        if cnt >= 1_000_000:
            return f"{cnt / 1_000_000:.1f}M"
        if cnt >= 1000:
            return f"{round(cnt / 1000)}K"
        return str(cnt)

    def get_engagement(self, obj) -> float:
        """
        Average engagement rate across connected platforms.
        
        :param obj: CreatorProfile instance.
        :return: Rounded average engagement percentage, 0.0 if none available.
        """
        # Step 1: Calculate arithmetic mean of engagement rates across non-deleted accounts
        accs = obj.social_accounts.filter(is_deleted=False)
        rates = [sa.engagement_rate for sa in accs if sa.engagement_rate]
        if rates:
            return round(sum(rates) / len(rates), 1)
        return 0.0

    def get_verified(self, obj) -> bool:
        """Verification badge clearance."""
        return obj.verification_status == VerificationStatus.VERIFIED

    def get_available(self, obj) -> bool:
        """Acceptance of new brand opportunities."""
        return obj.status == ProfileStatus.ACTIVE

    def get_startingPrice(self, obj):
        """
        Minimum base service fee across commercial packages.
        
        :param obj: CreatorProfile instance.
        :return: Lowest package starting price integer, or None if no services listed.
        """
        # Step 1: Find lowest active pricing package
        srv = obj.services.filter(is_deleted=False).order_by('starting_price_cents').first()
        if srv and srv.starting_price_cents:
            return srv.starting_price_cents // 100
        return None

    def get_joined(self, obj) -> str:
        """Platform registration date in ISO format."""
        return obj.created_at.strftime("%Y-%m-%d") if obj.created_at else ""

    def get_position(self, obj) -> str:
        """Avatar background positioning for responsive sprite rendering."""
        if obj.preferences and isinstance(obj.preferences, dict):
            return obj.preferences.get('sprite_position', '50% 50%')
        return '50% 50%'

    def get_accent(self, obj) -> str:
        """Visual card accent theme color."""
        if obj.preferences and isinstance(obj.preferences, dict):
            return obj.preferences.get('accent_color', 'brand')
        return 'brand'


class PublicCreatorDetailSerializer(PublicCreatorListSerializer):
    """
    Public comprehensive creator detail serializer for dedicated profile pages.
    Nests active portfolio media showcase, bookable rate card packages, and past clients.
    """
    services = serializers.SerializerMethodField()
    portfolio = serializers.SerializerMethodField()
    collaborations = serializers.SerializerMethodField()
    testimonials = serializers.SerializerMethodField()

    class Meta(PublicCreatorListSerializer.Meta):
        fields = PublicCreatorListSerializer.Meta.fields + [
            'about',
            'services',
            'portfolio',
            'collaborations',
            'testimonials'
        ]

    def get_services(self, obj) -> list:
        """
        Bookable commercial deliverables with pricing configured by the creator.
        
        :param obj: CreatorProfile instance.
        :return: List of service dictionaries, empty list if creator hasn't published rate card packages.
        """
        # Step 1: Query non-deleted service packages ordered by price
        srvs = obj.services.filter(is_deleted=False).order_by('starting_price_cents')
        return [
            {
                'id': str(s.id),
                'name': s.name,
                'description': s.description,
                'price': (s.starting_price_cents // 100) if s.starting_price_cents else None,
                'currency': obj.currency or 'INR',
                'delivery_time_days': getattr(s, 'turnaround_days', 5)
            }
            for s in srvs
        ]

    def get_portfolio(self, obj) -> list:
        """
        Showcase of previous commercial or creative media assets.
        
        :param obj: CreatorProfile instance.
        :return: List of media asset dictionaries, empty list if no items published.
        """
        # Step 1: Query active portfolio items ordered by custom sequence and creation date
        items = obj.portfolio_items.filter(is_deleted=False).order_by('order', '-created_at')
        return [
            {
                'id': str(item.id),
                'title': item.title,
                'caption': item.description,
                'media_type': item.media_type,
                'media_url': item.media_url,
                'thumbnail_url': item.media_url,
                'brand_name': item.brand_name,
                'format_tag': item.format_tag
            }
            for item in items
        ]

    def get_collaborations(self, obj) -> list:
        """
        List of corporate brand names creator has previously partnered with.
        
        :param obj: CreatorProfile instance.
        :return: List of brand names extracted from portfolio or preferences, empty list if none.
        """
        # Step 1: Extract unique brand tags from confirmed portfolio entries
        brands = set()
        for item in obj.portfolio_items.filter(is_deleted=False):
            if item.brand_name:
                brands.add(item.brand_name)
        if obj.preferences and isinstance(obj.preferences, dict) and 'collaborations' in obj.preferences:
            brands.update(obj.preferences['collaborations'])
        return list(brands)

    def get_testimonials(self, obj) -> list:
        """
        Verified quotes from brand marketing managers.
        
        :param obj: CreatorProfile instance.
        :return: List of client testimonial dictionaries, empty list if none published.
        """
        # Step 1: Load client quotes from creator preferences if configured
        if obj.preferences and isinstance(obj.preferences, dict) and 'testimonials' in obj.preferences:
            return obj.preferences['testimonials']
        return []



