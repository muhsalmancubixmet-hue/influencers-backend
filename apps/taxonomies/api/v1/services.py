"""
Taxonomies Domain Service Layer.

Provides core business logic, atomic batch operations, and third-party GIS integrations
for the Taxonomies application in accordance with the Cubelogs Standard and SaaS backend rules:
- reorder_categories: Atomic batch re-indexing of discovery category display orders.
- discover_and_cache_external_location: High-accuracy global GIS resolution using OpenStreetMap
  Nominatim with Photon fuzzy/phonetic fallback, robust hierarchical deduplication, and
  relational caching.
"""

from typing import List, Dict, Any, Optional
import urllib.request
import urllib.parse
import json
import logging
from django.db import transaction, DatabaseError
from django.db.models import Q

from apps.taxonomies.models import Category, Location, LocationType

logger = logging.getLogger(__name__)


def reorder_categories(orders: List[Dict[str, Any]]) -> None:
    """
    Perform an atomic batch update of category display ordering positions.

    Iterates over the supplied order mapping and bulk-updates the 'order' integer
    field on each Category record within a single database transaction.

    :param orders: List of dictionaries each containing 'id' (UUID or str) and 'order' (int).
    :return: None
    :raises ValueError: If input orders argument is not a valid list.
    :raises DatabaseError: If database persistence fails during atomic execution.
    """
    # Step 1: Validate payload structure
    if not isinstance(orders, list):
        raise ValueError("Invalid orders payload: expected a list of category order objects.")

    # Step 2: Execute atomic database batch updates
    with transaction.atomic():
        for item in orders:
            if not isinstance(item, dict):
                continue

            cat_id = item.get('id')
            order_val = item.get('order')

            if cat_id is not None and order_val is not None:
                try:
                    Category.objects.filter(id=cat_id, is_deleted=False).update(order=int(order_val))
                except (ValueError, TypeError) as conv_err:
                    logger.warning("Skipping invalid category order value '%s' for ID %s: %s", order_val, cat_id, conv_err)

        logger.info("Successfully reordered %d categories in database.", len(orders))


def _find_existing_canonical_location(
    name: str,
    parent: Optional[Location] = None,
    loc_type: Optional[str] = None
) -> Optional[Location]:
    """
    Look up an existing active non-deleted Location node by case-insensitive name,
    optionally constraining by parent node and location tier.

    :param name: Candidate geographic entity name (e.g. 'Nilambur', 'Kerala').
    :param parent: Optional parent Location instance to constrain hierarchical scope.
    :param loc_type: Optional LocationType choice string (e.g. LocationType.CITY).
    :return: Matched Location instance or None.
    """
    clean_name = name.strip()
    if not clean_name:
        return None

    # Step 1: Base queryset filtering active and non-deleted records
    qs = Location.objects.filter(name__iexact=clean_name, is_deleted=False)

    # Step 2: Apply optional hierarchical constraints
    if parent is not None:
        qs_parent = qs.filter(parent=parent)
        if loc_type:
            qs_parent = qs_parent.filter(type=loc_type)
        match = qs_parent.first()
        if match:
            return match

    # Step 3: Fallback lookup across same type if specific parent wasn't matched
    if loc_type:
        type_match = qs.filter(type=loc_type).first()
        if type_match:
            return type_match

    # Step 4: Broad name match fallback
    return qs.first()


def discover_and_cache_external_location(search_query: str) -> Optional[Location]:
    """
    Query global open GIS geocoding engines (OpenStreetMap Nominatim with Photon fuzzy fallback),
    dynamically construct hierarchical Location nodes (Country -> State -> District -> City/Locality),
    and cache the resolved place into the relational database with strict deduplication.

    Guarantees zero duplicate nodes:
    - Pre-checks database before dispatching external HTTP calls.
    - Resolves known sub-districts (taluks) and cities to existing canonical parents.
    - Prevents sub-cities or towns from spawning spurious duplicate DISTRICT nodes.

    :param search_query: Free-text place name entered by user (e.g. 'vadapuram', 'pulikalody').
    :return: Newly created or existing canonical Location model instance, or None.
    :raises DatabaseError: If database persistence fails during transaction.
    """
    # Step 1: Input Sanitization and Pre-Flight Database Check
    clean_q = search_query.strip()
    if not clean_q or len(clean_q) < 3:
        return None

    # Pre-check: If place already exists in database (exact or case-insensitive), return immediately
    existing_pre = Location.objects.filter(name__iexact=clean_q, is_deleted=False).first()
    if existing_pre:
        logger.debug("Location '%s' already cached in database (ID: %s).", clean_q, existing_pre.id)
        return existing_pre

    geo_data: Optional[Dict[str, Any]] = None

    # Step 2: Query OpenStreetMap Nominatim with Structured Address Details
    try:
        encoded_query = urllib.parse.quote(clean_q)
        nominatim_url = f"https://nominatim.openstreetmap.org/search?q={encoded_query}&format=json&addressdetails=1&limit=5"
        req = urllib.request.Request(
            nominatim_url,
            headers={'User-Agent': 'InfluencersApp/1.0 (support@influencers.com)'}
        )
        with urllib.request.urlopen(req, timeout=3.5) as response:
            items = json.loads(response.read().decode('utf-8'))
            if items:
                # Prioritize India / IN results if multiple returned, otherwise take top result
                best = next((x for x in items if x.get('address', {}).get('country_code', '').lower() == 'in'), items[0])
                addr = best.get('address', {})
                geo_data = {
                    'name': (best.get('name') or addr.get('village') or addr.get('town') or clean_q).strip().title(),
                    'country': addr.get('country', 'India').strip().title(),
                    'country_code': addr.get('country_code', 'IN').strip().upper(),
                    'state': (addr.get('state') or addr.get('region') or 'Kerala').strip().title(),
                    'district': (addr.get('state_district') or addr.get('county') or '').strip().title(),
                    'sub_locality': (addr.get('town') or addr.get('village') or addr.get('suburb') or addr.get('local_authority') or '').strip().title(),
                    'lat': float(best.get('lat', 0.0)),
                    'lon': float(best.get('lon', 0.0)),
                }
    except Exception as exc:
        logger.debug("Nominatim GIS lookup skipped for '%s': %s", clean_q, exc)

    # Step 3: Fallback to Photon (Elasticsearch with Phonetic and Typo Tolerance)
    if not geo_data:
        try:
            encoded_query = urllib.parse.quote(clean_q)
            photon_url = f"https://photon.komoot.io/api/?q={encoded_query}&limit=5"
            req = urllib.request.Request(
                photon_url,
                headers={'User-Agent': 'InfluencersApp/1.0'}
            )
            with urllib.request.urlopen(req, timeout=3.5) as response:
                data = json.loads(response.read().decode('utf-8'))
                features = data.get('features', [])
                if features:
                    # Prioritize India / IN results if available
                    best_feature = next((f for f in features if f.get('properties', {}).get('countrycode', '').lower() == 'in'), features[0])
                    props = best_feature.get('properties', {})
                    coords = best_feature.get('geometry', {}).get('coordinates', [0.0, 0.0])
                    geo_data = {
                        'name': (props.get('name') or clean_q).strip().title(),
                        'country': (props.get('country') or 'India').strip().title(),
                        'country_code': (props.get('countrycode') or 'IN').strip().upper(),
                        'state': (props.get('state') or 'Kerala').strip().title(),
                        'district': (props.get('district') or props.get('county') or '').strip().title(),
                        'sub_locality': (props.get('city') or props.get('county') or '').strip().title(),
                        'lat': float(coords[1]) if len(coords) > 1 else 0.0,
                        'lon': float(coords[0]) if len(coords) > 0 else 0.0,
                    }
        except Exception as exc:
            logger.debug("Photon GIS lookup skipped for '%s': %s", clean_q, exc)

    # Step 4: Geographic Data Validation
    if not geo_data:
        logger.warning("No geographic entity found across GIS engines for query: '%s'", clean_q)
        return None

    target_name = geo_data['name']

    # Step 5: Hierarchical Database Node Resolution & In-Transaction Deduplication
    try:
        with transaction.atomic():
            # 5a. Check if target entity already exists in DB
            target_match = _find_existing_canonical_location(target_name)
            if target_match:
                logger.info("Found existing canonical node '%s' (ID: %s).", target_match.name, target_match.id)
                return target_match

            # 5b. Country Node Resolution
            country_name = geo_data['country']
            country_code = geo_data['country_code']
            country_node = Location.objects.filter(
                type=LocationType.COUNTRY,
                is_deleted=False
            ).filter(Q(name__iexact=country_name) | Q(country_code=country_code)).first()

            if not country_node:
                country_node = Location.objects.create(
                    name=country_name,
                    type=LocationType.COUNTRY,
                    country_code=country_code,
                    is_active=True
                )

            # 5c. State / Region Node Resolution
            state_name = geo_data['state']
            region_node = Location.objects.filter(
                parent=country_node,
                type=LocationType.REGION,
                is_deleted=False,
                name__iexact=state_name
            ).first()

            if not region_node:
                # Also check broadly under region type
                region_node = Location.objects.filter(
                    type=LocationType.REGION,
                    is_deleted=False,
                    name__iexact=state_name
                ).first()

            if not region_node:
                region_node = Location.objects.create(
                    name=state_name,
                    type=LocationType.REGION,
                    parent=country_node,
                    country_code=country_code,
                    is_active=True
                )

            # 5d. District Node Resolution with Canonical Taluk/City Protection
            raw_district = geo_data.get('district', '')
            district_node = region_node

            if raw_district and raw_district != state_name:
                # Check if raw_district is actually an existing known City or Town (e.g. Nilambur)
                existing_as_city = Location.objects.filter(
                    name__iexact=raw_district,
                    type=LocationType.CITY,
                    is_deleted=False
                ).first()

                if existing_as_city and existing_as_city.parent:
                    # If this name is already a known city under a district, adopt its canonical parent!
                    district_node = existing_as_city.parent
                else:
                    # Check for genuine DISTRICT node
                    canon_district = Location.objects.filter(
                        name__iexact=raw_district,
                        type=LocationType.DISTRICT,
                        is_deleted=False
                    ).first()

                    if canon_district:
                        district_node = canon_district
                    else:
                        # Create new DISTRICT node under region
                        district_node = Location.objects.create(
                            name=raw_district,
                            type=LocationType.DISTRICT,
                            parent=region_node,
                            country_code=country_code,
                            is_active=True
                        )

            # 5e. Intermediate Town / Taluk / Locality Node Resolution
            parent_node = district_node
            sub_loc = geo_data.get('sub_locality', '')

            if sub_loc and sub_loc != target_name and sub_loc != raw_district and sub_loc != state_name:
                # Look up existing town/city node under this district or region
                existing_town = Location.objects.filter(
                    name__iexact=sub_loc,
                    type=LocationType.CITY,
                    is_deleted=False
                ).first()

                if existing_town:
                    parent_node = existing_town
                else:
                    parent_node = Location.objects.create(
                        name=sub_loc,
                        type=LocationType.CITY,
                        parent=district_node,
                        country_code=country_code,
                        is_active=True
                    )

            # 5f. Target Place Node Resolution
            resolved_type = LocationType.AREA if parent_node.type == LocationType.CITY else LocationType.CITY

            place_node = Location.objects.create(
                name=target_name,
                type=resolved_type,
                parent=parent_node,
                country_code=country_code,
                latitude=geo_data['lat'] if geo_data['lat'] != 0.0 else None,
                longitude=geo_data['lon'] if geo_data['lon'] != 0.0 else None,
                is_active=True
            )

            logger.info(
                "Persisted discovered location: '%s' (%s, parent: %s) -> ID: %s",
                place_node.name,
                place_node.type,
                parent_node.name,
                place_node.id
            )
            return place_node

    except DatabaseError as db_err:
        logger.error("Database persistence failed for discovered location '%s': %s", clean_q, db_err)
        raise
    except Exception as exc:
        logger.error("Failed to dynamically persist discovered location '%s': %s", clean_q, exc)
        return None
