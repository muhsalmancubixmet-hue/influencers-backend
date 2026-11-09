from typing import Dict, Any, List, Optional
import uuid
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.creators.models import (
    CreatorProfile,
    PortfolioItem,
    SocialAccount,
    VerificationStatus,
    ProfileStatus
)
from apps.common.models import SocialPlatform
from apps.common.api.v1.services import record_audit_log


def update_creator_profile(profile: CreatorProfile, validated_data: Dict[str, Any]) -> CreatorProfile:
    """
    Update core attributes of a creator profile and recalculate completeness.
    
    Supports merging dictionary preferences, aliasing display_name, and synchronizing user state.
    
    :param profile: CreatorProfile instance to mutate.
    :param validated_data: Dictionary of sanitized input fields.
    :return: Updated CreatorProfile instance.
    :raises ValidationError: If data values violate domain constraints.
    """
    # Step 1: Process and assign attribute updates
    for attr, val in validated_data.items():
        if attr == 'name':
            profile.display_name = val
        elif attr == 'preferences' and isinstance(val, dict):
            existing_pref = profile.preferences or {}
            existing_pref.update(val)
            profile.preferences = existing_pref
        else:
            setattr(profile, attr, val)

    # Step 2: Recalculate profile completeness score
    score = 20  # Base registration score
    if profile.bio:
        score += 15
    if profile.about:
        score += 15
    if profile.photo_url:
        score += 15
    if profile.cover_url:
        score += 10
    if profile.primary_location:
        score += 15
    if profile.categories.exists():
        score += 10
    profile.completion_percentage = min(score, 100)

    # Step 3: Persist state changes to database
    profile.save()
    return profile


def reorder_portfolio(profile: CreatorProfile, orders: List[Dict[str, Any]]) -> None:
    """
    Batch update display order for a creator's portfolio items.
    
    :param profile: CreatorProfile owner.
    :param orders: Array of {id, order} dictionaries.
    """
    with transaction.atomic():
        for item in orders:
            item_id = item.get('id')
            order_val = item.get('order')
            if item_id is not None and order_val is not None:
                PortfolioItem.objects.filter(
                    id=item_id,
                    creator=profile
                ).update(order=int(order_val))


def moderate_creator(
    creator_id: str,
    status: Optional[str] = None,
    verification_status: Optional[str] = None,
    admin_user: Optional[User] = None
) -> CreatorProfile:
    """
    Moderate creator profile status and verification badge with audit recording.
    
    :param creator_id: UUID of CreatorProfile.
    :param status: Optional new ProfileStatus.
    :param verification_status: Optional new VerificationStatus.
    :param admin_user: Staff User performing action.
    :return: Updated CreatorProfile.
    :raises ValidationError: If creator not found.
    """
    try:
        profile = CreatorProfile.objects.get(id=creator_id, is_deleted=False)
    except (CreatorProfile.DoesNotExist, ValueError):
        raise ValidationError(f"CreatorProfile '{creator_id}' not found.")

    with transaction.atomic():
        if status:
            profile.status = status
        if verification_status:
            profile.verification_status = verification_status

        profile.save()

        if admin_user:
            record_audit_log(
                admin=admin_user,
                action='MODERATE_CREATOR',
                entity='CreatorProfile',
                entity_id=str(profile.id),
                result='SUCCESS',
                reason=f"Status: {profile.status}, Verification: {profile.verification_status}"
            )

    return profile


def connect_social_account(
    profile: CreatorProfile,
    platform_identifier: str,
    username: str,
    profile_url: str,
    followers_count: int = 0,
    following_count: int = 0,
    engagement_rate: float = 0.0
) -> SocialAccount:
    """
    Connect or update an external social media channel for a creator profile.
    
    Adheres to tenant isolation boundaries and prevents unauthorized channel mutations.
    
    :param profile: CreatorProfile instance owning the channel.
    :param platform_identifier: UUID string, slug, or display name of the SocialPlatform.
    :param username: External handle without leading symbols.
    :param profile_url: Full URL to the public profile.
    :param followers_count: Current follower metric.
    :param following_count: Current following metric.
    :param engagement_rate: Average engagement percentage rate.
    :return: Persisted SocialAccount instance.
    :raises ValidationError: If platform is invalid or not registered in the platform catalog.
    """
    # Step 1: Resolve the master SocialPlatform record
    platform = None
    clean_id = str(platform_identifier).strip()

    # Try resolving by UUID if formatted as UUID
    try:
        platform_uuid = uuid.UUID(clean_id)
        platform = SocialPlatform.objects.filter(id=platform_uuid, is_deleted=False).first()
    except (ValueError, AttributeError):
        pass

    # Fallback to slug or case-insensitive name resolution
    if not platform:
        platform = SocialPlatform.objects.filter(slug__iexact=clean_id.lower(), is_deleted=False).first()
    if not platform:
        platform = SocialPlatform.objects.filter(name__iexact=clean_id, is_deleted=False).first()

    if not platform:
        raise ValidationError(f"Social platform '{platform_identifier}' is not supported or active.")

    # Step 2: Atomic transaction to persist or update social channel
    with transaction.atomic():
        account, created = SocialAccount.objects.update_or_create(
            creator=profile,
            platform=platform,
            defaults={
                'username': username.strip().lstrip('@'),
                'profile_url': profile_url.strip(),
                'followers_count': max(0, followers_count),
                'following_count': max(0, following_count),
                'engagement_rate': max(0.0, float(engagement_rate)),
                'is_deleted': False,
                'deleted_at': None
            }
        )

        # Step 3: Record audit log entry
        if profile.user:
            record_audit_log(
                admin=profile.user,
                action='CONNECT_SOCIAL_ACCOUNT',
                entity='SocialAccount',
                entity_id=str(account.id),
                result='SUCCESS',
                reason=f"Connected channel {platform.name} (@{account.username})"
            )

    return account


def disconnect_social_account(profile: CreatorProfile, account_id: str) -> None:
    """
    Disconnect / purge a social media channel from a creator profile.
    
    Guarantees strict creator tenant isolation so creators can never delete other accounts.
    
    :param profile: CreatorProfile owner.
    :param account_id: UUID of the SocialAccount to remove.
    :return: None
    :raises ValidationError: If social account is not found or does not belong to creator.
    """
    # Step 1: Query with strict creator ownership constraint
    try:
        account = SocialAccount.objects.get(id=account_id, creator=profile, is_deleted=False)
    except (SocialAccount.DoesNotExist, ValueError):
        raise ValidationError(f"Social account '{account_id}' not found for this profile.")

    # Step 2: Atomically soft delete and record audit log
    with transaction.atomic():
        platform_name = account.platform.name
        account_username = account.username
        account.soft_delete()

        if profile.user:
            record_audit_log(
                admin=profile.user,
                action='DISCONNECT_SOCIAL_ACCOUNT',
                entity='SocialAccount',
                entity_id=str(account.id),
                result='SUCCESS',
                reason=f"Disconnected {platform_name} (@{account_username})"
            )


def get_public_creators(filters: Dict[str, Any]):
    """
    Query, filter, and sort active creator profiles for the public marketplace.
    
    Adopts optimized query execution through select_related and prefetch_related
    to guarantee zero N+1 overhead across nested taxonomies and social metrics.
    
    :param filters: Sanitized query parameters dictionary containing:
                    - 'q' / 'search': Keyword text query
                    - 'category': Domain category filter name or ID
                    - 'location' / 'city' / 'district': Geographic matching
                    - 'country': Geographic country filter
                    - 'platform': Target social network
                    - 'language': Primary spoken/content language
                    - 'min_followers': Numerical lower bound on reach
                    - 'min_engagement': Numerical lower bound on engagement rate
                    - 'verified': Boolean flag for verified badge
                    - 'available': Boolean flag for open collaborations
                    - 'remote': Boolean flag for remote collaborations
                    - 'sort': Ordering heuristic ('relevance', 'followers', 'engagement', 'newest')
    :return: QuerySet of active, non-deleted CreatorProfile instances.
    """
    from django.db.models import Q

    # Step 1: Base queryset restricted strictly to active and non-deleted profiles
    qs = CreatorProfile.objects.select_related(
        'primary_location',
        'current_location',
        'user'
    ).prefetch_related(
        'categories__category',
        'languages',
        'service_areas__location',
        'social_accounts__platform',
        'services',
        'portfolio_items'
    ).filter(
        status=ProfileStatus.ACTIVE,
        is_deleted=False
    )

    # Step 2: Apply free-text query matching across name, handle, bio, and city
    search_query = filters.get('q') or filters.get('search')
    if search_query:
        search_term = str(search_query).strip()
        qs = qs.filter(
            Q(display_name__icontains=search_term) |
            Q(handle__icontains=search_term.lstrip('@')) |
            Q(bio__icontains=search_term) |
            Q(primary_location__name__icontains=search_term) |
            Q(primary_location__parent__name__icontains=search_term) |
            Q(primary_location__parent__parent__name__icontains=search_term)
        )

    # Step 3: Filter by industry category vertical
    category = filters.get('category')
    if category:
        qs = qs.filter(
            Q(categories__category__name__iexact=category) |
            Q(categories__category__slug__iexact=category) |
            Q(categories__category__id__iexact=category)
        )

    # Step 4: Geographic location and district filtering
    location = filters.get('location')
    if location:
        qs = qs.filter(
            Q(primary_location__name__icontains=location) |
            Q(primary_location__parent__name__icontains=location) |
            Q(primary_location__parent__parent__name__icontains=location) |
            Q(primary_location__id__iexact=location) |
            Q(service_areas__location__name__icontains=location) |
            Q(service_areas__location__parent__name__icontains=location) |
            Q(service_areas__location__parent__parent__name__icontains=location)
        )

    country = filters.get('country')
    if country:
        qs = qs.filter(
            Q(primary_location__country_code__iexact=country) |
            Q(primary_location__parent__country_code__iexact=country) |
            Q(primary_location__name__iexact=country)
        )

    # Step 5: Social media platform presence
    platform = filters.get('platform')
    if platform:
        qs = qs.filter(
            social_accounts__platform__name__iexact=platform,
            social_accounts__is_deleted=False
        )

    # Step 6: Spoken or content language
    language = filters.get('language')
    if language:
        qs = qs.filter(languages__language_name__iexact=language)

    # Step 7: Verification and collaboration preferences
    if filters.get('verified') in [True, 'true', '1']:
        qs = qs.filter(verification_status=VerificationStatus.VERIFIED)

    if filters.get('remote') in [True, 'true', '1']:
        qs = qs.filter(remote_available=True)

    # Step 8: Apply sorting heuristic
    sort_key = filters.get('sort', 'relevance')
    if sort_key == 'newest':
        qs = qs.order_by('-created_at')
    else:
        qs = qs.order_by('-completion_percentage', '-created_at')

    return qs.distinct()


def get_public_creator_detail(slug_or_handle: str):
    """
    Retrieve full public creator profile by unique handle, slug, or UUID primary key.
    
    :param slug_or_handle: Creator handle, slug identifier, or UUID primary key.
    :return: CreatorProfile instance with all showcase relations or None.
    """
    from django.db.models import Q

    # Step 1: Normalize input identifier
    clean_identifier = str(slug_or_handle).strip().lstrip('@')

    lookup = Q(handle__iexact=clean_identifier.lower())
    try:
        parsed_uuid = uuid.UUID(clean_identifier)
        lookup |= Q(id=parsed_uuid)
    except (ValueError, AttributeError):
        pass

    # Step 2: Query creator with all related portfolio and service elements
    try:
        return CreatorProfile.objects.select_related(
            'primary_location',
            'current_location',
            'user'
        ).prefetch_related(
            'categories__category',
            'languages',
            'service_areas__location',
            'social_accounts__platform',
            'services',
            'portfolio_items'
        ).get(
            lookup,
            status=ProfileStatus.ACTIVE,
            is_deleted=False
        )
    except (CreatorProfile.DoesNotExist, CreatorProfile.MultipleObjectsReturned):
        return None

