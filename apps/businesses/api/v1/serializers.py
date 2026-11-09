from rest_framework import serializers

from apps.businesses.models import (
    BusinessProfile,
    BusinessVerificationStatus,
    BusinessStatus,
    BusinessShortlist,
    ShortlistEntry,
    BusinessSavedSearch
)
from apps.taxonomies.api.v1.serializers import LocationSerializer


class BusinessProfileSerializer(serializers.ModelSerializer):
    """Detailed serializer for business profile."""
    email = serializers.EmailField(source='user.email', read_only=True)
    hq_location_details = LocationSerializer(source='hq_location', read_only=True)

    class Meta:
        model = BusinessProfile
        fields = [
            'id',
            'email',
            'company_name',
            'business_type',
            'hq_location',
            'hq_location_details',
            'contact_name',
            'contact_email',
            'contact_phone',
            'about',
            'logo_url',
            'tax_id',
            'verification_status',
            'status',
            'notification_preferences',
            'created_at'
        ]
        read_only_fields = ['id', 'email', 'created_at']


class AdminBusinessListSerializer(serializers.ModelSerializer):
    """Tabular serializer for Control Panel brand / business accounts."""
    name = serializers.CharField(source='company_name', read_only=True)
    type = serializers.CharField(source='business_type', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    hq_city = serializers.CharField(source='hq_location.name', read_only=True, allow_null=True)
    location = serializers.SerializerMethodField()
    campaigns = serializers.SerializerMethodField()
    verification = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()

    subscription = serializers.SerializerMethodField()

    class Meta:
        model = BusinessProfile
        fields = [
            'id',
            'name',
            'type',
            'company_name',
            'business_type',
            'email',
            'contact_name',
            'contact_phone',
            'hq_city',
            'location',
            'campaigns',
            'subscription',
            'verification',
            'verification_status',
            'status',
            'joined',
            'created_at'
        ]

    def get_location(self, obj):
        loc = obj.hq_location
        city = loc.name if loc else "Remote"
        country_code = loc.country_code if loc else "US"
        return {
            "city": city,
            "country": "United States" if country_code == "US" else (country_code or "Global"),
            "countryCode": country_code
        }

    def get_subscription(self, obj):
        return "Free"

    def get_campaigns(self, obj):
        return obj.campaigns.filter(is_deleted=False).count()

    def get_verification(self, obj):
        return (obj.verification_status or "unverified").lower()

    def get_joined(self, obj):
        return obj.created_at.strftime("%b %d, %Y") if obj.created_at else ""



class AdminBusinessModerationSerializer(serializers.Serializer):
    """Payload contract for admin moderation of brand business status."""
    verification_status = serializers.ChoiceField(choices=BusinessVerificationStatus.choices, required=False)
    status = serializers.ChoiceField(choices=BusinessStatus.choices, required=False)


class BusinessOperatingLocationSerializer(serializers.ModelSerializer):
    """Serializer representing branch outlet or operational venue with radius targeting."""
    location_name = serializers.CharField(source='location.name', read_only=True, allow_null=True)
    location_country = serializers.CharField(source='location.country_code', read_only=True, allow_null=True)

    class Meta:
        from apps.businesses.models import BusinessOperatingLocation
        model = BusinessOperatingLocation
        fields = [
            'id',
            'label',
            'address',
            'location',
            'location_name',
            'location_country',
            'radius_km',
            'created_at'
        ]
        read_only_fields = ['id', 'location_name', 'location_country', 'created_at']


class BusinessRegistrationSerializer(serializers.Serializer):
    """
    Payload contract for brand/business public self-registration.
    Adheres strictly to BACKEND_ENGINEERING_RULES.md security standards.
    """
    company_name = serializers.CharField(max_length=200, help_text="Official business/brand trade name.")
    email = serializers.EmailField(help_text="Corporate business representative email address.")
    password = serializers.CharField(min_length=8, write_only=True, help_text="Account authentication password.")
    business_type = serializers.CharField(max_length=100, required=False, default="General", help_text="Industry vertical.")
    contact_name = serializers.CharField(max_length=150, required=False, allow_blank=True, help_text="Representative name.")
    contact_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, help_text="Contact phone number.")

    def validate_email(self, value: str) -> str:
        """Ensure email uniqueness across the platform."""
        clean = value.strip().lower()
        from apps.accounts.models import User
        if User.objects.filter(email=clean).exists():
            raise serializers.ValidationError("An account with this electronic mail address already exists.")
        return clean


class BusinessProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Payload contract for updating brand profile attributes.
    Restricted to authenticated business owners.
    """
    class Meta:
        model = BusinessProfile
        fields = [
            'company_name',
            'business_type',
            'hq_location',
            'contact_name',
            'contact_email',
            'contact_phone',
            'about',
            'logo_url',
            'tax_id',
            'notification_preferences'
        ]


class BusinessVerificationApplySerializer(serializers.Serializer):
    """
    Payload contract for submitting official brand verification documents and tax identifier.
    Transitions verification status to PENDING for platform administration review.
    """
    tax_id = serializers.CharField(max_length=50, help_text="Official GSTIN, VAT, or corporate EIN number.")
    official_website = serializers.URLField(max_length=500, required=False, allow_blank=True, help_text="Official corporate domain.")
    notes = serializers.CharField(required=False, allow_blank=True, help_text="Additional verification notes for reviewers.")


class ShortlistEntrySerializer(serializers.ModelSerializer):
    """Serializer representing a creator entry inside a shortlist."""
    creator_id = serializers.UUIDField(source='creator.id', read_only=True)
    creator_name = serializers.CharField(source='creator.display_name', read_only=True)
    creator_handle = serializers.CharField(source='creator.handle', read_only=True)
    creator_avatar = serializers.CharField(source='creator.photo_url', read_only=True)
    creator_category = serializers.CharField(source='creator.category', read_only=True)
    creator_location = serializers.CharField(source='creator.location_name', read_only=True)
    creator_bio = serializers.CharField(source='creator.bio', read_only=True)
    creator_verified = serializers.BooleanField(source='creator.verified', read_only=True)

    class Meta:
        model = ShortlistEntry
        fields = [
            'id',
            'creator_id',
            'creator_name',
            'creator_handle',
            'creator_avatar',
            'creator_category',
            'creator_location',
            'creator_bio',
            'creator_verified',
            'notes',
            'tags',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BusinessShortlistSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for business shortlists."""
    creators_count = serializers.SerializerMethodField()
    creator_avatars = serializers.SerializerMethodField()
    entries = ShortlistEntrySerializer(many=True, read_only=True)

    class Meta:
        model = BusinessShortlist
        fields = [
            'id',
            'name',
            'description',
            'color',
            'is_archived',
            'creators_count',
            'creator_avatars',
            'entries',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_creators_count(self, obj) -> int:
        return obj.entries.count()

    def get_creator_avatars(self, obj) -> list:
        return [
            entry.creator.photo_url for entry in obj.entries.select_related('creator')[:4]
            if entry.creator.photo_url
        ]


class BusinessShortlistCreateSerializer(serializers.ModelSerializer):
    """Payload contract for creating or updating a shortlist."""
    class Meta:
        model = BusinessShortlist
        fields = ['name', 'description', 'color']

    def validate_name(self, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise serializers.ValidationError("Shortlist name cannot be blank.")
        return clean


class BusinessSavedSearchSerializer(serializers.ModelSerializer):
    """
    Serializer contract for business saved creator discovery searches.
    
    Includes name, filter dictionary parameters, real-time alert notification status,
    and count of new matching creators discovered.
    """
    categories = serializers.SerializerMethodField()
    locations = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()
    platforms = serializers.SerializerMethodField()
    followers = serializers.SerializerMethodField()
    budget = serializers.SerializerMethodField()
    minEngagement = serializers.SerializerMethodField()
    notify = serializers.BooleanField(source='notify_enabled', required=False)
    newMatches = serializers.IntegerField(source='new_matches_count', read_only=True)

    class Meta:
        model = BusinessSavedSearch
        fields = [
            'id',
            'name',
            'filters',
            'notify',
            'notify_enabled',
            'newMatches',
            'new_matches_count',
            'categories',
            'locations',
            'languages',
            'platforms',
            'followers',
            'budget',
            'minEngagement',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'newMatches', 'new_matches_count']

    def get_categories(self, obj) -> list:
        return (obj.filters or {}).get('categories', [])

    def get_locations(self, obj) -> list:
        return (obj.filters or {}).get('locations', [])

    def get_languages(self, obj) -> list:
        return (obj.filters or {}).get('languages', [])

    def get_platforms(self, obj) -> list:
        return (obj.filters or {}).get('platforms', [])

    def get_followers(self, obj) -> list:
        return (obj.filters or {}).get('followers', [0, 5000000])

    def get_budget(self, obj) -> list:
        return (obj.filters or {}).get('budget', [0, 500000])

    def get_minEngagement(self, obj) -> float:
        return (obj.filters or {}).get('minEngagement', 0)


