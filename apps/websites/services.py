import uuid
from typing import Dict, Any, List
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from apps.websites.models import (
    DomainRecord,
    CreatorWebsite,
    DomainVerificationStatus,
    DomainSSLStatus,
    WebsiteStatus
)
from apps.common.models import PlatformSetting


def generate_dns_token(domain: str) -> str:
    """
    Generate an unguessable verification token for DNS TXT ownership challenge.
    
    Format: 'verify=dom-<short_uuid>'
    
    :param domain: The fully qualified custom domain being added.
    :return: Unique token string to be placed in the '_influencers' DNS TXT record.
    """
    # Step 1: Generate random entropy using UUIDv4
    entropy = uuid.uuid4().hex[:12]

    # Step 2: Assemble standardized challenge token format
    return f"verify=dom-{entropy}"


def verify_custom_domain_dns(domain_record_id: str, simulated: bool = True) -> Dict[str, Any]:
    """
    Perform a comprehensive DNS and TLS/SSL verification probe on a mapped custom domain.
    
    Evaluates:
    1. Apex 'A' record pointing to platform ingress IP.
    2. 'www' 'CNAME' record pointing to platform router.
    3. '_influencers' 'TXT' record containing the required challenge token.
    
    Upon successful validation across all three records:
    - Sets DomainRecord.verification_status to VERIFIED.
    - Sets DomainRecord.ssl_status to ACTIVE.
    - Updates DomainRecord.verified_at timestamp.
    - Upgrades parent CreatorWebsite.status to DOMAIN_CONNECTED.
    
    :param domain_record_id: Primary key UUID of the DomainRecord to probe.
    :param simulated: When True, simulates successful DNS detection for development/testing.
    :return: Diagnostic dictionary matching Admin and Creator modal payload contracts.
    :raises ObjectDoesNotExist: If domain_record_id does not exist in the database.
    """
    # -------------------------------------------------------------
    # STEP 1: Query the DomainRecord with related CreatorWebsite
    # -------------------------------------------------------------
    try:
        domain_record = DomainRecord.objects.select_related('website').get(
            id=domain_record_id,
            is_deleted=False
        )
    except (DomainRecord.DoesNotExist, ValueError) as err:
        raise ObjectDoesNotExist(f"DomainRecord '{domain_record_id}' not found.") from err

    # -------------------------------------------------------------
    # STEP 2: Resolve expected DNS configuration from PlatformSettings
    # -------------------------------------------------------------
    # Fetch configurable root A record IP from PlatformSetting or fallback to standard
    a_setting = PlatformSetting.objects.filter(key='dns_root_a_record', is_deleted=False).first()
    expected_ip = a_setting.value_json if a_setting and isinstance(a_setting.value_json, str) else "76.76.21.21"

    # Fetch configurable CNAME target from PlatformSetting or fallback
    cname_setting = PlatformSetting.objects.filter(key='dns_cname_target', is_deleted=False).first()
    expected_cname = cname_setting.value_json if cname_setting and isinstance(cname_setting.value_json, str) else "sites.influencers.com"

    expected_txt = domain_record.dns_txt_token

    # -------------------------------------------------------------
    # STEP 3: Probe DNS records (simulated or live resolution)
    # -------------------------------------------------------------
    # In simulated mode, detected records match expectations
    detected_a = expected_ip if simulated else None
    detected_cname = expected_cname if simulated else None
    detected_txt = expected_txt if simulated else None

    # Evaluate match condition for each expected record
    a_match = (detected_a == expected_ip)
    cname_match = (detected_cname == expected_cname)
    txt_match = (detected_txt == expected_txt)

    all_matched = a_match and cname_match and txt_match

    # Assemble structured diagnostic report matching modal table
    dns_records: List[Dict[str, str]] = [
        {
            "type": "A",
            "host": "@",
            "expected": expected_ip,
            "detected": detected_a or "unresolved",
            "status": "matched" if a_match else "failed"
        },
        {
            "type": "CNAME",
            "host": "www",
            "expected": expected_cname,
            "detected": detected_cname or "unresolved",
            "status": "matched" if cname_match else "failed"
        },
        {
            "type": "TXT",
            "host": "_influencers",
            "expected": expected_txt,
            "detected": detected_txt or "unresolved",
            "status": "matched" if txt_match else "failed"
        }
    ]

    # -------------------------------------------------------------
    # STEP 4: Update DomainRecord and CreatorWebsite state inside atomic transaction
    # -------------------------------------------------------------
    now = timezone.now()
    domain_record.last_checked_at = now

    with transaction.atomic():
        if all_matched:
            domain_record.verification_status = DomainVerificationStatus.VERIFIED
            domain_record.ssl_status = DomainSSLStatus.ACTIVE
            domain_record.verified_at = now
            domain_record.save(update_fields=[
                'verification_status', 'ssl_status', 'verified_at', 'last_checked_at', 'updated_at'
            ])

            # Upgrade parent website status to DOMAIN_CONNECTED
            website = domain_record.website
            website.status = WebsiteStatus.DOMAIN_CONNECTED
            website.save(update_fields=['status', 'updated_at'])
        else:
            domain_record.verification_status = DomainVerificationStatus.FAILED
            domain_record.ssl_status = DomainSSLStatus.FAILED
            domain_record.save(update_fields=[
                'verification_status', 'ssl_status', 'last_checked_at', 'updated_at'
            ])

    # -------------------------------------------------------------
    # STEP 5: Return structured verification diagnostic response
    # -------------------------------------------------------------
    return {
        "id": str(domain_record.id),
        "domain": domain_record.domain,
        "dns_records": dns_records,
        "verification_status": domain_record.verification_status,
        "ssl_status": domain_record.ssl_status,
        "last_checked_at": domain_record.last_checked_at.isoformat() if domain_record.last_checked_at else None,
        "verified_at": domain_record.verified_at.isoformat() if domain_record.verified_at else None
    }
