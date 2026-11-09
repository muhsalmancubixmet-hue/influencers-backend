"""
Database seeding command for authentic Kerala administrative hierarchy and locations.
Adheres strictly to BACKEND_ENGINEERING_RULES.md standards with typed signatures,
transaction atomicity, and full inline documentation.
"""
import logging
from typing import Any
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.taxonomies.models import Location, LocationType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Populates comprehensive Kerala districts, municipalities, and cities in the Location taxonomy hierarchy.
    """
    help = "Seeds comprehensive Kerala geographic taxonomy (Districts, Cities, Municipalities) under India > Kerala."

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Execute atomic location hierarchy generation.

        :param args: Positional command arguments.
        :param options: Keyword options passed from CLI.
        :return: None
        """
        self.stdout.write("Seeding comprehensive Kerala locations taxonomy...")

        with transaction.atomic():
            # Step 1: Ensure root Country node exists
            india, _ = Location.objects.get_or_create(
                name="India",
                type=LocationType.COUNTRY,
                defaults={
                    "country_code": "IN",
                    "latitude": 20.5937,
                    "longitude": 78.9629,
                    "is_active": True,
                }
            )

            # Step 2: Ensure state Region node exists
            kerala, _ = Location.objects.get_or_create(
                name="Kerala",
                type=LocationType.REGION,
                parent=india,
                defaults={
                    "country_code": "IN",
                    "latitude": 10.8505,
                    "longitude": 76.2711,
                    "is_active": True,
                }
            )

            # Step 3: Define 14 Kerala districts and their prominent cities / towns
            kerala_tree = {
                "Malappuram": {
                    "lat": 11.0510, "lng": 76.0711,
                    "cities": [
                        ("Nilambur", 11.2758, 76.2263),
                        ("Mampad", 11.2447, 76.1794),
                        ("Wandoor", 11.1947, 76.2345),
                        ("Edakkara", 11.3536, 76.3072),
                        ("Chungathara", 11.3142, 76.2625),
                        ("Vazhikkadavu", 11.3934, 76.3353),
                        ("Karulai", 11.2581, 76.2942),
                        ("Kalikavu", 11.1681, 76.3267),
                        ("Pandikkad", 11.1189, 76.2361),
                        ("Edavanna", 11.2167, 76.1333),
                        ("Areacode", 11.2356, 76.0506),
                        ("Manjeri", 11.1215, 76.1214),
                        ("Malappuram", 11.0732, 76.0740),
                        ("Perinthalmanna", 10.9760, 76.2254),
                        ("Tirur", 10.9146, 75.9229),
                        ("Kottakkal", 11.0006, 75.9984),
                        ("Ponnani", 10.7738, 75.9272),
                        ("Kondotty", 11.1449, 75.9629),
                        ("Edappal", 10.7601, 75.9868),
                        ("Valanchery", 10.8841, 76.0708),
                    ]
                },
                "Ernakulam": {
                    "lat": 9.9816, "lng": 76.2999,
                    "cities": [
                        ("Kochi", 9.9312, 76.2673),
                        ("Aluva", 10.1076, 76.3516),
                        ("Kakkanad", 10.0159, 76.3419),
                        ("Angamaly", 10.1960, 76.3860),
                        ("Muvattupuzha", 9.9894, 76.5789),
                        ("Perumbavoor", 10.1114, 76.4754),
                        ("Kothamangalam", 10.0617, 76.6264),
                    ]
                },
                "Kozhikode": {
                    "lat": 11.2588, "lng": 75.7804,
                    "cities": [
                        ("Kozhikode", 11.2588, 75.7804),
                        ("Vadakara", 11.6089, 75.5917),
                        ("Koyilandy", 11.4398, 75.6961),
                        ("Feroke", 11.1965, 75.8344),
                        ("Ramanattukara", 11.1736, 75.8675),
                    ]
                },
                "Thiruvananthapuram": {
                    "lat": 8.5241, "lng": 76.9366,
                    "cities": [
                        ("Thiruvananthapuram", 8.5241, 76.9366),
                        ("Attingal", 8.6960, 76.8143),
                        ("Neyyattinkara", 8.4005, 77.0863),
                        ("Varkala", 8.7379, 76.7163),
                        ("Nedumangad", 8.6017, 77.0006),
                    ]
                },
                "Thrissur": {
                    "lat": 10.5276, "lng": 76.2144,
                    "cities": [
                        ("Thrissur", 10.5276, 76.2144),
                        ("Chalakudy", 10.3070, 76.3330),
                        ("Guruvayur", 10.5946, 76.0408),
                        ("Kodungallur", 10.2312, 76.1966),
                        ("Kunnamkulam", 10.6517, 76.0740),
                        ("Irinjalakuda", 10.3429, 76.2084),
                    ]
                },
                "Palakkad": {
                    "lat": 10.7867, "lng": 76.6548,
                    "cities": [
                        ("Palakkad", 10.7867, 76.6548),
                        ("Ottapalam", 10.7744, 76.3789),
                        ("Shoranur", 10.7621, 76.2801),
                        ("Chittur", 10.6976, 76.7196),
                        ("Mannarkkad", 10.9897, 76.4589),
                    ]
                },
                "Kannur": {
                    "lat": 11.8745, "lng": 75.3704,
                    "cities": [
                        ("Kannur", 11.8745, 75.3704),
                        ("Thalassery", 11.7491, 75.4890),
                        ("Payyanur", 12.1009, 75.2014),
                        ("Taliparamba", 12.0463, 75.3578),
                        ("Mattannur", 11.9287, 75.5772),
                    ]
                },
                "Wayanad": {
                    "lat": 11.6854, "lng": 76.1320,
                    "cities": [
                        ("Kalpetta", 11.6103, 76.0827),
                        ("Sulthan Bathery", 11.6622, 76.2570),
                        ("Mananthavady", 11.8022, 76.0034),
                        ("Vythiri", 11.5510, 76.0379),
                        ("Meppadi", 11.5519, 76.1264),
                    ]
                },
                "Kottayam": {
                    "lat": 9.5916, "lng": 76.5222,
                    "cities": [
                        ("Kottayam", 9.5916, 76.5222),
                        ("Changanassery", 9.4449, 76.5383),
                        ("Pala", 9.7107, 76.6836),
                        ("Vaikom", 9.7498, 76.3960),
                        ("Ettumanoor", 9.6675, 76.5628),
                    ]
                },
                "Alappuzha": {
                    "lat": 9.4981, "lng": 76.3388,
                    "cities": [
                        ("Alappuzha", 9.4981, 76.3388),
                        ("Cherthala", 9.6844, 76.3308),
                        ("Kayamkulam", 9.1729, 76.5015),
                        ("Mavelikkara", 9.2435, 76.5507),
                        ("Chengannur", 9.3175, 76.6111),
                    ]
                },
                "Kollam": {
                    "lat": 8.8932, "lng": 76.6141,
                    "cities": [
                        ("Kollam", 8.8932, 76.6141),
                        ("Karunagappally", 9.0560, 76.5369),
                        ("Punalur", 9.0195, 76.9272),
                        ("Kottarakkara", 8.9984, 76.7725),
                        ("Paravur", 8.8105, 76.6710),
                    ]
                },
                "Kasaragod": {
                    "lat": 12.4996, "lng": 74.9869,
                    "cities": [
                        ("Kasaragod", 12.4996, 74.9869),
                        ("Kanhangad", 12.3082, 75.0934),
                        ("Nileshwaram", 12.2536, 75.1325),
                        ("Cheruvathur", 12.2155, 75.1610),
                    ]
                },
                "Idukki": {
                    "lat": 9.8494, "lng": 76.9804,
                    "cities": [
                        ("Munnar", 10.0889, 77.0595),
                        ("Thodupuzha", 9.8959, 76.7184),
                        ("Kattappana", 9.7505, 77.1197),
                        ("Nedumkandam", 9.8375, 77.1517),
                        ("Painavu", 9.8475, 76.9272),
                    ]
                },
                "Pathanamthitta": {
                    "lat": 9.2648, "lng": 76.7870,
                    "cities": [
                        ("Pathanamthitta", 9.2648, 76.7870),
                        ("Thiruvalla", 9.3835, 76.5741),
                        ("Adoor", 9.1530, 76.7337),
                        ("Ranni", 9.3809, 76.8153),
                        ("Konni", 9.2272, 76.8488),
                    ]
                },
            }

            created_count = 0
            for district_name, d_info in kerala_tree.items():
                # Create or fetch District node
                district_node, created = Location.objects.get_or_create(
                    name=district_name,
                    type=LocationType.DISTRICT,
                    parent=kerala,
                    defaults={
                        "country_code": "IN",
                        "latitude": d_info["lat"],
                        "longitude": d_info["lng"],
                        "is_active": True,
                    }
                )
                if created:
                    created_count += 1

                # Create all child Cities / Municipalities under District
                for city_name, c_lat, c_lng in d_info["cities"]:
                    # Also re-parent existing cities if they were directly under Kerala
                    existing_city = Location.objects.filter(
                        name__iexact=city_name,
                        type=LocationType.CITY
                    ).first()

                    if existing_city:
                        existing_city.parent = district_node
                        existing_city.latitude = c_lat
                        existing_city.longitude = c_lng
                        existing_city.is_active = True
                        existing_city.save(update_fields=["parent", "latitude", "longitude", "is_active"])
                    else:
                        Location.objects.create(
                            name=city_name,
                            type=LocationType.CITY,
                            parent=district_node,
                            country_code="IN",
                            latitude=c_lat,
                            longitude=c_lng,
                            is_active=True
                        )
                        created_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully populated Kerala locations hierarchy! Total new nodes created: {created_count}. Total nodes in DB: {Location.objects.count()}."
                )
            )

