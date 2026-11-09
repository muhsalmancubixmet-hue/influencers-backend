from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.creators.models import CreatorProfile
from apps.websites.models import (
    CreatorWebsite,
    WebsiteSection,
    DomainRecord,
    DomainType,
    DomainVerificationStatus,
    DomainSSLStatus,
    WebsiteStatus
)
from apps.websites.services import generate_dns_token, verify_custom_domain_dns


def get_or_create_creator_website(creator: CreatorProfile) -> CreatorWebsite:
    """
    Ensure creator has an initialized website entity with default standard sections.
    
    :param creator: CreatorProfile instance.
    :return: CreatorWebsite instance.
    """
    website, created = CreatorWebsite.objects.get_or_create(
        creator=creator,
        defaults={
            'title': creator.display_name,
            'tagline': creator.bio or 'Creator & Storyteller',
        }
    )

    if created:
        # Seed 5 standard modular blocks
        standard_sections = [
            ('Hero', 0, {'headline': creator.display_name, 'show_avatar': True}),
            ('About', 1, {'bio': creator.bio, 'show_socials': True}),
            ('Portfolio', 2, {'grid_columns': 3}),
            ('Services', 3, {'show_rates': True}),
            ('Contact', 4, {'form_enabled': True}),
        ]
        for name, order, config in standard_sections:
            WebsiteSection.objects.create(
                website=website,
                section_name=name,
                order=order,
                config_json=config
            )

    return website


def update_website_settings(website: CreatorWebsite, data: Dict[str, Any]) -> CreatorWebsite:
    """
    Update theme styling, branding colors, typography, or publishing toggle.
    
    :param website: CreatorWebsite instance.
    :param data: Dictionary of attributes.
    :return: Updated CreatorWebsite.
    """
    is_pub = data.get('is_published')
    target_status = data.get('status')

    if target_status == WebsiteStatus.PUBLISHED or is_pub is True:
        website.is_published = True
        website.status = WebsiteStatus.PUBLISHED
        if not website.published_at:
            website.published_at = timezone.now()
    elif target_status == WebsiteStatus.DRAFT or is_pub is False:
        website.is_published = False
        website.status = WebsiteStatus.DRAFT

    for field in ['template', 'title', 'tagline', 'accent_color', 'font_family', 'layout_style']:
        if field in data and data[field] is not None:
            setattr(website, field, data[field])

    website.save()
    return website


def connect_website_domain(website: CreatorWebsite, domain: str) -> DomainRecord:
    """
    Map a custom domain to creator website and generate TXT verification token.
    
    :param website: CreatorWebsite instance.
    :param domain: FQDN domain string (e.g. 'ananyanair.com').
    :return: Created or existing DomainRecord.
    :raises ValidationError: If domain is already mapped to another active website.
    """
    clean_domain = domain.lower().strip().replace('https://', '').replace('http://', '').strip('/')

    existing = DomainRecord.objects.filter(domain=clean_domain, is_deleted=False).exclude(website=website).first()
    if existing:
        raise ValidationError(f"Domain '{clean_domain}' is already connected to another creator website.")

    token = generate_dns_token(clean_domain)

    with transaction.atomic():
        domain_record, created = DomainRecord.objects.update_or_create(
            website=website,
            domain=clean_domain,
            defaults={
                'domain_type': DomainType.CUSTOM,
                'verification_status': DomainVerificationStatus.PENDING,
                'ssl_status': DomainSSLStatus.PENDING,
                'dns_txt_token': token
            }
        )

        website.status = WebsiteStatus.DOMAIN_PENDING
        website.save(update_fields=['status', 'updated_at'])

    return domain_record
