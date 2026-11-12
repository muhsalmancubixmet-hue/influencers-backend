import datetime
from django.core.management.base import BaseCommand
from apps.businesses.models import BusinessProfile
from apps.campaigns.models import Campaign, CampaignStatus, EscrowStatus
from apps.taxonomies.models import Category, Location


class Command(BaseCommand):
    help = "Seed published campaigns for all active business accounts with cover images."

    def handle(self, *args, **options):
        self.stdout.write("Seeding and syncing campaigns for all registered businesses...")

        # Helper lookups
        cat_fashion = Category.objects.filter(name__iexact='Fashion').first()
        cat_food = Category.objects.filter(name__iexact='Food').first()
        cat_tech = Category.objects.filter(name__iexact='Technology').first()
        cat_travel = Category.objects.filter(name__iexact='Travel').first()
        cat_edu = Category.objects.filter(name__iexact='Education').first()

        loc_kochi = Location.objects.filter(name__icontains='Kochi').first() or Location.objects.filter(name__icontains='Aluva').first()
        loc_thrissur = Location.objects.filter(name__icontains='Thrissur').first() or loc_kochi
        loc_alappuzha = Location.objects.filter(name__icontains='Alappuzha').first() or loc_kochi

        # Update existing 3 campaigns with cover images
        c_hills = Campaign.objects.filter(title__icontains='hills').first()
        if c_hills:
            c_hills.cover_image_url = 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80'
            c_hills.save(update_fields=['cover_image_url'])
            self.stdout.write(f"Updated cover for: {c_hills.title}")

        c_flavours = Campaign.objects.filter(title__icontains='Monsoon flavours').first()
        if c_flavours:
            c_flavours.cover_image_url = 'https://images.unsplash.com/photo-1589302168068-964664d93dc0?auto=format&fit=crop&w=1200&q=80'
            c_flavours.save(update_fields=['cover_image_url'])
            self.stdout.write(f"Updated cover for: {c_flavours.title}")

        c_akshara = Campaign.objects.filter(title__icontains='Learning made local').first()
        if c_akshara:
            c_akshara.cover_image_url = 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?auto=format&fit=crop&w=1200&q=80'
            c_akshara.save(update_fields=['cover_image_url'])
            self.stdout.write(f"Updated cover for: {c_akshara.title}")

        # Now ensure Kalyan Silks, Kochi Cafe, cublogs, cubixmet have campaigns
        biz_configs = [
            {
                "company_name": "Kalyan Silks",
                "title": "Onam Silk Fest & Heritage Weaves",
                "category": cat_fashion,
                "location": loc_thrissur,
                "location_text": "Thrissur & Ernakulam, Kerala",
                "cover_image_url": "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=1200&q=80",
                "total_budget_cents": 15000000,  # ₹1,50,000
                "currency": "INR",
                "creators_needed": 3,
                "objective": "Celebrate Kerala handloom craftsmanship and contemporary silk fashion for the festive season.",
                "target_audience": "Fashion-conscious men and women in South India and NRI Malayali diaspora.",
                "deliverables_spec": "2 Reels (60s) + 5 High-res Photos showcasing the bridal silk and festive kasavu collections.",
                "deadline": datetime.date(2026, 12, 25),
                "is_featured": True,
            },
            {
                "company_name": "Kochi Cafe",
                "title": "Artisanal Coffee & Coastal Brunch Series",
                "category": cat_food,
                "location": loc_kochi,
                "location_text": "Fort Kochi, Ernakulam",
                "cover_image_url": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80",
                "total_budget_cents": 4500000,  # ₹45,000
                "currency": "INR",
                "creators_needed": 2,
                "objective": "Highlight our specialty roastery, cold brew cocktails, and colonial heritage cafe ambience.",
                "target_audience": "Local foodies, travelers, cafe lovers, and creators visiting Fort Kochi.",
                "deliverables_spec": "1 Dedicated 4K Reel + 3 Story highlights covering the barista experience and weekend brunch.",
                "deadline": datetime.date(2026, 12, 15),
                "is_featured": False,
            },
            {
                "company_name": "cublogs",
                "title": "Developer Storytelling & Tech Insights",
                "category": cat_tech,
                "location": loc_kochi,
                "location_text": "Kochi & Remote Worldwide",
                "cover_image_url": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=1200&q=80",
                "total_budget_cents": 8000000,  # ₹80,000
                "currency": "INR",
                "creators_needed": 2,
                "objective": "Showcase modern software architecture and developer workflows through relatable creator stories.",
                "target_audience": "Software engineers, tech leads, tech founders, and computer science students.",
                "deliverables_spec": "1 Long-form YouTube breakdown (8-10m) + 1 LinkedIn technical carousel post.",
                "deadline": datetime.date(2026, 12, 30),
                "is_featured": False,
            },
            {
                "company_name": "cubixmet",
                "title": "Creator Growth & Analytics Masterclass",
                "category": cat_tech,
                "location": loc_kochi,
                "location_text": "Infopark Kochi & Remote",
                "cover_image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80",
                "total_budget_cents": 12000000,  # ₹1,20,000
                "currency": "INR",
                "creators_needed": 4,
                "objective": "Demonstrate data-driven brand collaboration metrics and creator workspace tools.",
                "target_audience": "Digital creators, influencers, talent managers, and agencies.",
                "deliverables_spec": "2 Instagram Reels + 1 Community post reviewing analytics features and campaign tracking.",
                "deadline": datetime.date(2027, 1, 15),
                "is_featured": True,
            },
        ]

        for cfg in biz_configs:
            biz = BusinessProfile.objects.filter(company_name__iexact=cfg["company_name"]).first()
            if not biz:
                self.stdout.write(self.style.WARNING(f"Business '{cfg['company_name']}' not found. Skipping."))
                continue

            camp, created = Campaign.objects.get_or_create(
                business=biz,
                title=cfg["title"],
                defaults={
                    "category": cfg["category"],
                    "location": cfg["location"],
                    "location_text": cfg["location_text"],
                    "cover_image_url": cfg["cover_image_url"],
                    "total_budget_cents": cfg["total_budget_cents"],
                    "currency": cfg["currency"],
                    "creators_needed": cfg["creators_needed"],
                    "objective": cfg["objective"],
                    "target_audience": cfg["target_audience"],
                    "deliverables_spec": cfg["deliverables_spec"],
                    "deadline": cfg["deadline"],
                    "status": CampaignStatus.PUBLISHED,
                    "escrow_status": EscrowStatus.PENDING,
                    "is_featured": cfg["is_featured"],
                }
            )

            if not created:
                camp.cover_image_url = cfg["cover_image_url"]
                camp.status = CampaignStatus.PUBLISHED
                camp.total_budget_cents = cfg["total_budget_cents"]
                camp.deliverables_spec = cfg["deliverables_spec"]
                camp.objective = cfg["objective"]
                camp.location_text = cfg["location_text"]
                camp.save()
                self.stdout.write(f"Updated existing campaign: {camp.title} for {biz.company_name}")
            else:
                self.stdout.write(self.style.SUCCESS(f"Created new campaign: {camp.title} for {biz.company_name}"))

        self.stdout.write(self.style.SUCCESS("All business campaigns successfully seeded and published!"))

