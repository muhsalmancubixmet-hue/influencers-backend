import uuid
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User, UserRole
from apps.taxonomies.models import Category, Location, LocationType
from apps.creators.models import (
    CreatorProfile,
    CreatorCategory,
    CreatorLanguage,
    CreatorServiceArea,
    SocialAccount,
    CreatorService,
    PortfolioItem,
    PortfolioMediaType,
    ProfileStatus,
    VerificationStatus
)
from apps.common.models import SocialPlatform
from apps.businesses.models import BusinessProfile
from apps.campaigns.models import Campaign, CampaignStatus


class Command(BaseCommand):
    help = "Seeds authentic Kerala marketplace creators, campaigns, and locations."

    def handle(self, *args, **options):
        self.stdout.write("Starting Kerala Marketplace data seeding...")

        with transaction.atomic():
            # 1. Seed or resolve Social Platforms
            platforms_map = {}
            for plat_name, icon in [
                ("Instagram", "instagram"),
                ("YouTube", "youtube"),
                ("TikTok", "video"),
                ("Facebook", "facebook"),
                ("LinkedIn", "linkedin"),
                ("Pinterest", "image")
            ]:
                p, _ = SocialPlatform.objects.get_or_create(
                    name=plat_name,
                    defaults={'icon': icon, 'is_active': True}
                )
                platforms_map[plat_name] = p

            # 2. Seed or resolve Hierarchical Countries, Regions, and Cities
            india, _ = Location.objects.get_or_create(
                name="India",
                defaults={"type": LocationType.COUNTRY, "country_code": "IN", "is_active": True}
            )
            kerala, _ = Location.objects.get_or_create(
                name="Kerala",
                defaults={"type": LocationType.REGION, "parent": india, "country_code": "IN", "is_active": True}
            )
            uae, _ = Location.objects.get_or_create(
                name="United Arab Emirates",
                defaults={"type": LocationType.COUNTRY, "country_code": "AE", "is_active": True}
            )
            uk, _ = Location.objects.get_or_create(
                name="United Kingdom",
                defaults={"type": LocationType.COUNTRY, "country_code": "GB", "is_active": True}
            )
            us, _ = Location.objects.get_or_create(
                name="United States",
                defaults={"type": LocationType.COUNTRY, "country_code": "US", "is_active": True}
            )
            singapore_c, _ = Location.objects.get_or_create(
                name="Singapore",
                defaults={"type": LocationType.COUNTRY, "country_code": "SG", "is_active": True}
            )

            kerala_places = [
                {"city": "Kochi", "parent": kerala, "country_code": "IN", "lat": 9.9312, "lng": 76.2673},
                {"city": "Kozhikode", "parent": kerala, "country_code": "IN", "lat": 11.2588, "lng": 75.7804},
                {"city": "Thrissur", "parent": kerala, "country_code": "IN", "lat": 10.5276, "lng": 76.2144},
                {"city": "Thiruvananthapuram", "parent": kerala, "country_code": "IN", "lat": 8.5241, "lng": 76.9366},
                {"city": "Kottayam", "parent": kerala, "country_code": "IN", "lat": 9.5916, "lng": 76.5222},
                {"city": "Wayanad", "parent": kerala, "country_code": "IN", "lat": 11.6085, "lng": 76.0830},
                {"city": "Dubai", "parent": uae, "country_code": "AE", "lat": 25.2048, "lng": 55.2708},
                {"city": "London", "parent": uk, "country_code": "GB", "lat": 51.5072, "lng": -0.1276},
                {"city": "New York", "parent": us, "country_code": "US", "lat": 40.7128, "lng": -74.0060},
                {"city": "Singapore City", "parent": singapore_c, "country_code": "SG", "lat": 1.3521, "lng": 103.8198},
            ]
            locations_map = {}
            for pl in kerala_places:
                loc, _ = Location.objects.get_or_create(
                    name=pl["city"],
                    defaults={
                        "type": LocationType.CITY,
                        "parent": pl["parent"],
                        "country_code": pl["country_code"],
                        "latitude": Decimal(str(pl["lat"])),
                        "longitude": Decimal(str(pl["lng"])),
                        "is_active": True
                    }
                )
                locations_map[pl["city"]] = loc

            # 3. Seed Categories
            category_names = [
                "Food", "Travel", "Fashion", "Beauty", "Lifestyle",
                "Fitness", "Technology", "Gaming", "Education", "Photography",
                "Comedy", "Entertainment", "Parenting", "Business", "Local Creators"
            ]
            categories_map = {}
            for idx, cname in enumerate(category_names):
                cat, _ = Category.objects.get_or_create(
                    name=cname,
                    defaults={"order": idx, "is_active": True}
                )
                categories_map[cname] = cat

            # 4. Seed Creators
            creators_data = [
                {
                    "name": "Maya Menon",
                    "handle": "mayatasteskerala",
                    "email": "maya.menon@influencers.demo",
                    "category": "Food",
                    "city": "Kochi",
                    "bio": "Food storyteller tracing home kitchens, new cafés and the people behind every plate.",
                    "followers": 248000,
                    "engagement": 6.8,
                    "verified": True,
                    "reel": 18000,
                    "story": 6500,
                    "languages": ["Malayalam", "English"],
                    "platforms": ["Instagram", "YouTube"],
                    "sprite_pos": "0% 50%",
                    "accent": "coral"
                },
                {
                    "name": "Arjun Nair",
                    "handle": "arjuntrails",
                    "email": "arjun.nair@influencers.demo",
                    "category": "Travel",
                    "city": "Kozhikode",
                    "bio": "Slow travel, hidden trails and cinematic stories from India and beyond.",
                    "followers": 412000,
                    "engagement": 5.4,
                    "verified": True,
                    "reel": 28000,
                    "story": 9000,
                    "languages": ["Malayalam", "English", "Hindi"],
                    "platforms": ["Instagram", "YouTube"],
                    "sprite_pos": "33.33% 50%",
                    "accent": "green"
                },
                {
                    "name": "Diya Varma",
                    "handle": "diyainframe",
                    "email": "diya.varma@influencers.demo",
                    "category": "Fashion",
                    "city": "Thrissur",
                    "bio": "Contemporary regional style, conscious labels and occasionwear with an editorial eye.",
                    "followers": 186000,
                    "engagement": 7.2,
                    "verified": True,
                    "reel": 22000,
                    "story": 7000,
                    "languages": ["Malayalam", "English"],
                    "platforms": ["Instagram", "Pinterest"],
                    "sprite_pos": "66.66% 50%",
                    "accent": "gold"
                },
                {
                    "name": "Rohan Joseph",
                    "handle": "rohanreviews",
                    "email": "rohan.joseph@influencers.demo",
                    "category": "Technology",
                    "city": "Kochi",
                    "bio": "Useful tech, cameras and creator tools explained simply.",
                    "followers": 325000,
                    "engagement": 4.9,
                    "verified": True,
                    "reel": 32000,
                    "story": 10000,
                    "languages": ["Malayalam", "English"],
                    "platforms": ["YouTube", "Instagram"],
                    "sprite_pos": "100% 50%",
                    "accent": "blue"
                },
                {
                    "name": "Nayana K",
                    "handle": "nayanaglow",
                    "email": "nayana.k@influencers.demo",
                    "category": "Beauty",
                    "city": "Kozhikode",
                    "bio": "Honest beauty reviews and warm-weather skincare for every skin tone.",
                    "followers": 154000,
                    "engagement": 8.1,
                    "verified": True,
                    "reel": 16000,
                    "story": 5500,
                    "languages": ["Malayalam", "English"],
                    "platforms": ["Instagram", "YouTube"],
                    "sprite_pos": "0% 50%",
                    "accent": "rose"
                },
                {
                    "name": "Akhil Dev",
                    "handle": "akhilmoves",
                    "email": "akhil.dev@influencers.demo",
                    "category": "Fitness",
                    "city": "Thiruvananthapuram",
                    "bio": "Approachable strength, mobility and sustainable everyday fitness.",
                    "followers": 98000,
                    "engagement": 9.3,
                    "verified": False,
                    "reel": 12000,
                    "story": 4000,
                    "languages": ["Malayalam", "English"],
                    "platforms": ["Instagram", "TikTok"],
                    "sprite_pos": "33.33% 50%",
                    "accent": "lime"
                },
                {
                    "name": "Sreelakshmi R",
                    "handle": "littlethingsbysree",
                    "email": "sreelakshmi.r@influencers.demo",
                    "category": "Parenting",
                    "city": "Kottayam",
                    "bio": "Gentle parenting, playful learning and honest notes from family life.",
                    "followers": 121000,
                    "engagement": 7.7,
                    "verified": False,
                    "reel": 14000,
                    "story": 4500,
                    "languages": ["Malayalam", "English"],
                    "platforms": ["Instagram", "Facebook"],
                    "sprite_pos": "66.66% 50%",
                    "accent": "mint"
                },
                {
                    "name": "Jishnu Joy",
                    "handle": "jishnujokes",
                    "email": "jishnu.joy@influencers.demo",
                    "category": "Comedy",
                    "city": "Thrissur",
                    "bio": "Everyday characters, quick sketches and culture-led comedy.",
                    "followers": 538000,
                    "engagement": 10.2,
                    "verified": True,
                    "reel": 35000,
                    "story": 12000,
                    "languages": ["Malayalam"],
                    "platforms": ["Instagram", "YouTube"],
                    "sprite_pos": "100% 50%",
                    "accent": "orange"
                }
            ]

            for cdata in creators_data:
                user, _ = User.objects.get_or_create(
                    email=cdata["email"],
                    defaults={
                        "username": cdata["handle"],
                        "first_name": cdata["name"],
                        "role": UserRole.CREATOR,
                        "is_active": True
                    }
                )

                loc = locations_map.get(cdata["city"])
                cat = categories_map.get(cdata["category"])

                profile, _ = CreatorProfile.objects.update_or_create(
                    handle=cdata["handle"],
                    defaults={
                        "user": user,
                        "display_name": cdata["name"],
                        "bio": cdata["bio"],
                        "about": f"{cdata['name']} is one of Kerala's leading content creators in {cdata['category']}, partnering with regional and national brands to tell meaningful stories.",
                        "primary_location": loc,
                        "current_location": loc,
                        "status": ProfileStatus.ACTIVE,
                        "verification_status": VerificationStatus.VERIFIED if cdata["verified"] else VerificationStatus.UNVERIFIED,
                        "travel_available": True,
                        "remote_available": True,
                        "completion_percentage": 95,
                        "currency": "INR",
                        "preferences": {
                            "sprite_position": cdata["sprite_pos"],
                            "accent_color": cdata["accent"],
                            "collaborations": ["Nila Foods", "Fernway Stays", "Sahra Atelier", "Nova Mobile"]
                        }
                    }
                )

                # Assign Category
                if cat:
                    CreatorCategory.objects.get_or_create(
                        creator=profile,
                        category=cat
                    )

                # Assign Languages
                lang_code_map = {"Malayalam": "ml", "English": "en", "Hindi": "hi", "Arabic": "ar"}
                for lang_name in cdata["languages"]:
                    code = lang_code_map.get(lang_name, lang_name[:2].lower())
                    CreatorLanguage.objects.get_or_create(
                        creator=profile,
                        language_code=code
                    )

                # Assign Social Channels
                for plat_name in cdata["platforms"]:
                    plat = platforms_map.get(plat_name)
                    if plat:
                        SocialAccount.objects.update_or_create(
                            creator=profile,
                            platform=plat,
                            defaults={
                                "username": cdata["handle"],
                                "followers_count": cdata["followers"] // len(cdata["platforms"]),
                                "engagement_rate": Decimal(str(cdata["engagement"])),
                                "is_verified": cdata["verified"]
                            }
                        )

                # Assign Services / Rate Card
                CreatorService.objects.update_or_create(
                    creator=profile,
                    name="Brand Reel",
                    defaults={
                        "description": "Concept, shoot, edit and one collaborative Instagram short-form video.",
                        "deliverables_spec": "1 Instagram Reel, collaborative tag",
                        "starting_price_cents": cdata["reel"] * 100,
                        "turnaround_days": 5
                    }
                )
                CreatorService.objects.update_or_create(
                    creator=profile,
                    name="Story Set",
                    defaults={
                        "description": "Three narrative story frames with link sticker and brand mention.",
                        "deliverables_spec": "3 Instagram Story frames",
                        "starting_price_cents": cdata["story"] * 100,
                        "turnaround_days": 2
                    }
                )
                CreatorService.objects.update_or_create(
                    creator=profile,
                    name="Event Appearance",
                    defaults={
                        "description": "On-location store launch or festival appearance with real-time story coverage.",
                        "deliverables_spec": "Store visit, 4 stories, 1 post",
                        "starting_price_cents": 0,
                        "turnaround_days": 1
                    }
                )

                # Assign Portfolio Sample
                PortfolioItem.objects.get_or_create(
                    creator=profile,
                    title=f"{cdata['category']} Showcase",
                    defaults={
                        "media_type": PortfolioMediaType.IMAGE,
                        "media_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80",
                        "brand_name": "Nila Foods",
                        "format_tag": cdata['category'],
                        "order": 0
                    }
                )

            # 5. Seed Kerala Business Campaigns
            campaigns_data = [
                {
                    "title": "Monsoon flavours of Malabar",
                    "brand": "Nila Foods",
                    "email": "marketing@nilafoods.demo",
                    "category": "Food",
                    "city": "Kozhikode",
                    "platform": ["Instagram"],
                    "budget": 45000,
                    "creators": 3,
                    "deadline": "2026-10-18",
                    "deliverables": ["2 reels", "4 stories"],
                    "description": "Celebrate regional Malabar monsoon recipes through personal, story-led culinary content."
                },
                {
                    "title": "A weekend in the hills",
                    "brand": "Fernway Stays",
                    "email": "stays@fernway.demo",
                    "category": "Travel",
                    "city": "Wayanad",
                    "platform": ["Instagram", "YouTube"],
                    "budget": 50000,
                    "creators": 2,
                    "deadline": "2026-10-24",
                    "deliverables": ["1 vlog", "2 reels"],
                    "description": "An immersive two-night resort story for couples, young professionals, and slow travellers."
                },
                {
                    "title": "Learning made local",
                    "brand": "Akshara Learn",
                    "email": "growth@aksharalearn.demo",
                    "category": "Education",
                    "city": "Kochi",
                    "platform": ["YouTube"],
                    "budget": 35000,
                    "creators": 4,
                    "deadline": "2026-11-02",
                    "deliverables": ["1 integration", "3 shorts"],
                    "description": "Introduce native-language learning tools and exam prep to students and parents."
                }
            ]

            for camp in campaigns_data:
                b_user, _ = User.objects.get_or_create(
                    email=camp["email"],
                    defaults={
                        "username": camp["brand"].lower().replace(" ", ""),
                        "first_name": camp["brand"],
                        "role": UserRole.BUSINESS,
                        "is_active": True
                    }
                )
                b_profile, _ = BusinessProfile.objects.update_or_create(
                    user=b_user,
                    defaults={
                        "company_name": camp["brand"],
                        "contact_name": f"{camp['brand']} Marketing",
                        "business_type": camp["category"],
                        "contact_email": camp["email"],
                        "hq_location": locations_map.get(camp["city"])
                    }
                )

                Campaign.objects.update_or_create(
                    title=camp["title"],
                    business=b_profile,
                    defaults={
                        "category": categories_map.get(camp["category"]),
                        "location": locations_map.get(camp["city"]),
                        "location_text": f"{camp['city']}, Kerala",
                        "total_budget_cents": camp["budget"] * 100,
                        "currency": "INR",
                        "creators_needed": camp["creators"],
                        "objective": camp["description"],
                        "deliverables_spec": " · ".join(camp["deliverables"]),
                        "status": CampaignStatus.PUBLISHED,
                        "is_featured": True
                    }
                )

        self.stdout.write(self.style.SUCCESS("Successfully seeded Kerala marketplace data!"))
