from rest_framework import serializers

from apps.campaigns.models import (
    Campaign,
    CampaignBid,
    Requirement,
    Inquiry,
    InquiryMessage,
    CampaignStatus,
    EscrowStatus
)


class CampaignBidSerializer(serializers.ModelSerializer):
    """
    Serializer representing creator campaign application bid.
    Exposes creator details, financial quotations, and pitch proposals.
    """
    creator_name = serializers.CharField(source='creator.display_name', read_only=True)
    creator_handle = serializers.CharField(source='creator.handle', read_only=True)
    creator_photo = serializers.CharField(source='creator.photo_url', read_only=True)
    name = serializers.CharField(source='creator.display_name', read_only=True)
    handle = serializers.CharField(source='creator.handle', read_only=True)
    avatar = serializers.CharField(source='creator.photo_url', read_only=True)
    fee = serializers.SerializerMethodField()
    currency = serializers.CharField(source='campaign.currency', read_only=True)
    date = serializers.SerializerMethodField()
    pitch_text = serializers.CharField(source='pitch', read_only=True)

    class Meta:
        model = CampaignBid
        fields = [
            'id',
            'campaign',
            'creator',
            'creator_name',
            'creator_handle',
            'creator_photo',
            'name',
            'handle',
            'avatar',
            'proposed_fee_cents',
            'fee',
            'currency',
            'pitch',
            'pitch_text',
            'status',
            'date',
            'created_at'
        ]
        read_only_fields = ['id', 'creator', 'creator_name', 'creator_handle', 'creator_photo', 'created_at']

    def get_fee(self, obj: CampaignBid) -> int:
        """
        Derive whole-unit quotation fee from cents.

        :param obj: CampaignBid instance.
        :return: Integer fee in major currency units.
        """
        return (obj.proposed_fee_cents or 0) // 100

    def get_date(self, obj: CampaignBid) -> str:
        """
        Format submission timestamp for card UI representation.

        :param obj: CampaignBid instance.
        :return: Short human-readable date string (e.g. 'Nov 09').
        """
        return obj.created_at.strftime("%b %d") if obj.created_at else ""


class CampaignListSerializer(serializers.ModelSerializer):
    """Tabular and card serializer for campaigns and creator discovery."""
    business_name = serializers.CharField(source='business.company_name', read_only=True)
    business_logo = serializers.CharField(source='business.logo_url', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    business = serializers.CharField(source='business.company_name', read_only=True)
    business_id = serializers.UUIDField(source='business.id', read_only=True)
    category = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    budget = serializers.SerializerMethodField()
    creators = serializers.IntegerField(source='creators_needed', read_only=True)
    location = serializers.CharField(source='location_text', read_only=True)
    deliverables = serializers.CharField(source='deliverables_spec', read_only=True)
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    platform = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            'id',
            'business',
            'business_id',
            'business_name',
            'business_logo',
            'title',
            'category',
            'category_name',
            'location',
            'location_text',
            'cover_image_url',
            'budget',
            'total_budget_cents',
            'currency',
            'creators',
            'creators_needed',
            'applications_count',
            'deliverables',
            'platform',
            'lat',
            'lng',
            'deadline',
            'status',
            'escrow_status',
            'is_featured',
            'created_at'
        ]
        read_only_fields = ['id', 'business_name', 'business_logo', 'category_name', 'created_at']

    def get_budget(self, obj):
        return (obj.total_budget_cents or 0) // 100

    def get_lat(self, obj):
        if obj.location and obj.location.latitude:
            return float(obj.location.latitude)
        text = (obj.location_text or '').lower()
        if 'kochi' in text or 'cochin' in text or 'ernakulam' in text: return 9.9312
        if 'wayanad' in text: return 11.6854
        if 'kozhikode' in text or 'calicut' in text: return 11.2588
        if 'trivandrum' in text or 'thiruvananthapuram' in text: return 8.5241
        if 'munnar' in text: return 10.0889
        if 'kerala' in text: return 10.8505
        if 'dubai' in text: return 25.2048
        return 9.9312

    def get_lng(self, obj):
        if obj.location and obj.location.longitude:
            return float(obj.location.longitude)
        text = (obj.location_text or '').lower()
        if 'kochi' in text or 'cochin' in text or 'ernakulam' in text: return 76.2673
        if 'wayanad' in text: return 76.1320
        if 'kozhikode' in text or 'calicut' in text: return 75.7804
        if 'trivandrum' in text or 'thiruvananthapuram' in text: return 76.9366
        if 'munnar' in text: return 77.0595
        if 'kerala' in text: return 76.2711
        if 'dubai' in text: return 55.2708
        return 76.2673

    def get_platform(self, obj):
        spec = (obj.deliverables_spec or '').lower()
        platforms = []
        if any(w in spec for w in ['reel', 'story', 'stories', 'post', 'instagram']):
            platforms.append('Instagram')
        if any(w in spec for w in ['youtube', 'vlog', 'short', 'shorts']):
            platforms.append('YouTube')
        if 'tiktok' in spec:
            platforms.append('TikTok')
        return ', '.join(platforms) if platforms else 'Instagram, YouTube'



class CampaignDetailSerializer(CampaignListSerializer):
    """Comprehensive campaign details including objectives, brief, and deliverables."""
    bids = CampaignBidSerializer(many=True, read_only=True)

    class Meta(CampaignListSerializer.Meta):
        fields = CampaignListSerializer.Meta.fields + [
            'objective',
            'target_audience',
            'deliverables_spec',
            'bids'
        ]


class RequirementSerializer(serializers.ModelSerializer):
    """Serializer representing public brand requirements."""
    business_name = serializers.CharField(source='business.company_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    budget_min_cents = serializers.IntegerField(source='min_budget_cents', read_only=True)
    budget_max_cents = serializers.IntegerField(source='max_budget_cents', read_only=True)
    proposals_count = serializers.IntegerField(source='applications_count', read_only=True)

    class Meta:
        model = Requirement
        fields = [
            'id',
            'business',
            'business_name',
            'title',
            'category',
            'category_name',
            'min_budget_cents',
            'max_budget_cents',
            'budget_min_cents',
            'budget_max_cents',
            'currency',
            'creators_needed',
            'location_text',
            'status',
            'applications_count',
            'proposals_count',
            'description',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'business_name', 'category_name', 'proposals_count', 'applications_count', 'created_at']


class CreatorOpportunityApplySerializer(serializers.Serializer):
    """Payload contract for creator submitting bid proposal on campaign opportunity."""
    proposed_fee_cents = serializers.IntegerField(min_value=1)
    pitch_text = serializers.CharField(min_length=10)


class InquiryMessageSerializer(serializers.ModelSerializer):
    """Serializer representing messages in a direct brand-creator inquiry thread."""
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_email = serializers.EmailField(source='sender.email', read_only=True)
    offer_price_cents = serializers.IntegerField(source='inquiry.budget_cents', read_only=True)
    is_from_business = serializers.SerializerMethodField()
    is_from_brand = serializers.SerializerMethodField()
    is_from_creator = serializers.SerializerMethodField()
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = InquiryMessage
        fields = [
            'id',
            'sender',
            'sender_name',
            'sender_email',
            'body',
            'offer_price_cents',
            'is_from_business',
            'is_from_brand',
            'is_from_creator',
            'is_me',
            'created_at'
        ]
        read_only_fields = ['id', 'sender', 'sender_name', 'sender_email', 'created_at']

    def get_is_from_business(self, obj) -> bool:
        return hasattr(obj.sender, 'business_profile') or getattr(obj.sender, 'role', '') == 'BUSINESS'

    def get_is_from_brand(self, obj) -> bool:
        return self.get_is_from_business(obj)

    def get_is_from_creator(self, obj) -> bool:
        return hasattr(obj.sender, 'creator_profile') or getattr(obj.sender, 'role', '') == 'CREATOR'

    def get_is_me(self, obj) -> bool:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.sender_id == request.user.id
        return False


class InquirySerializer(serializers.ModelSerializer):
    """Serializer for inquiries between brands and creators."""
    business_name = serializers.CharField(source='business.company_name', read_only=True)
    creator_id = serializers.UUIDField(source='creator.id', read_only=True)
    creator_name = serializers.CharField(source='creator.display_name', read_only=True)
    creator_handle = serializers.CharField(source='creator.handle', read_only=True)
    creator_avatar = serializers.CharField(source='creator.photo_url', read_only=True)
    messages_count = serializers.IntegerField(source='messages.count', read_only=True)
    business = serializers.CharField(source='business.company_name', read_only=True)
    business_id = serializers.UUIDField(source='business.id', read_only=True)
    is_read = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    campaign = serializers.SerializerMethodField()
    budget = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    latest_message_at = serializers.SerializerMethodField()

    class Meta:
        model = Inquiry
        fields = [
            'id',
            'business',
            'business_id',
            'business_name',
            'creator_id',
            'creator_name',
            'creator_handle',
            'creator_avatar',
            'campaign',
            'subject',
            'message',
            'budget',
            'budget_cents',
            'currency',
            'status',
            'is_read',
            'unread_count',
            'date',
            'latest_message_at',
            'messages_count',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'business_name',
            'creator_id',
            'creator_name',
            'creator_handle',
            'creator_avatar',
            'is_read',
            'unread_count',
            'messages_count',
            'latest_message_at',
            'created_at'
        ]

    def get_unread_count(self, obj) -> int:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return obj.messages.filter(is_read=False).count()

    def get_is_read(self, obj) -> bool:
        return self.get_unread_count(obj) == 0

    def get_campaign(self, obj):
        return obj.campaign.title if obj.campaign else obj.subject

    def get_budget(self, obj):
        val = (obj.budget_cents or 0) // 100
        curr = obj.currency or 'INR'
        sym = '₹' if curr == 'INR' else '$'
        return f"{sym}{val:,}"

    def get_date(self, obj):
        return obj.created_at.strftime("%b %d, %Y") if obj.created_at else ""

    def get_message(self, obj):
        first_msg = obj.messages.order_by('created_at').first()
        return first_msg.body if first_msg else obj.subject

    def get_latest_message_at(self, obj):
        latest = obj.messages.order_by('-created_at').first()
        return latest.created_at if latest else obj.updated_at


class PublicCampaignListSerializer(serializers.ModelSerializer):
    """
    Public marketplace serializer for open campaigns and commercial briefs.
    
    Transforms internal Campaign models into the schema expected by the
    public marketplace CampaignCard and discovery filters.
    """
    business = serializers.CharField(source='business.company_name', read_only=True)
    category = serializers.CharField(source='category.name', read_only=True, default="General")
    location = serializers.SerializerMethodField()
    remote = serializers.SerializerMethodField()
    platform = serializers.SerializerMethodField()
    budgetMin = serializers.SerializerMethodField()
    budgetMax = serializers.SerializerMethodField()
    budgetNote = serializers.SerializerMethodField()
    deliverables = serializers.CharField(source='deliverables_spec', read_only=True)
    deadline = serializers.SerializerMethodField()
    creators = serializers.IntegerField(source='creators_needed', read_only=True)
    description = serializers.CharField(source='objective', read_only=True)
    image = serializers.CharField(source='cover_image_url', read_only=True)

    class Meta:
        model = Campaign
        fields = [
            'id',
            'title',
            'business',
            'category',
            'location',
            'remote',
            'platform',
            'currency',
            'budgetMin',
            'budgetMax',
            'budgetNote',
            'deliverables',
            'deadline',
            'creators',
            'description',
            'cover_image_url',
            'image',
        ]

    def get_location(self, obj):
        loc = obj.location
        if not loc:
            return None
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

    def get_remote(self, obj) -> bool:
        return obj.location is None

    def get_platform(self, obj) -> str:
        return "Instagram"

    def get_budgetMin(self, obj) -> int:
        return (obj.total_budget_cents or 3000000) // 100

    def get_budgetMax(self, obj):
        min_val = self.get_budgetMin(obj)
        return int(min_val * 1.5)

    def get_budgetNote(self, obj) -> str:
        return "+ deliverables"

    def get_deliverables(self, obj) -> str:
        if obj.deliverables and isinstance(obj.deliverables, list):
            return " · ".join(obj.deliverables)
        return "2 reels · 4 stories"

    def get_deadline(self, obj) -> str:
        return obj.deadline.strftime("%b %d") if obj.deadline else "Open"


class PublicCampaignDetailSerializer(PublicCampaignListSerializer):
    """
    Public comprehensive campaign detail serializer.
    Includes target audience, business background, and complete brief specification.
    """
    business_website = serializers.CharField(source='business.website', read_only=True, default="")
    target_audience = serializers.CharField(read_only=True, default="")
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta(PublicCampaignListSerializer.Meta):
        fields = PublicCampaignListSerializer.Meta.fields + [
            'business_website',
            'target_audience',
            'status',
            'created_at'
        ]



class PublicInquiryCreateSerializer(serializers.Serializer):
    """
    Validation payload contract for client inquiries submitted via public creator profile cards.
    """
    creator_handle = serializers.CharField(max_length=80)
    client_name = serializers.CharField(max_length=150)
    client_email = serializers.EmailField()
    client_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    company_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    subject = serializers.CharField(max_length=200)
    message = serializers.CharField()
    budget = serializers.IntegerField(required=False, min_value=0)
    currency = serializers.CharField(max_length=3, required=False, default="INR")
    service_id = serializers.CharField(required=False, allow_blank=True)


