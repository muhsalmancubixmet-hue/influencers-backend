from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import RoleTemplate, RolePermission, ModuleChoice, AccessLevel


class Command(BaseCommand):
    """
    Management command to populate and synchronize the 6 default system role templates
    and their exact 14-module clearance tiers into the database.
    
    Safe to execute multiple times (idempotent via update_or_create).
    """

    help = "Seeds standard 6-tier RBAC role templates and module permission matrix."

    # Standard matrix defining exact access tiers for all 6 administrative roles across 14 modules
    ROLE_PERMISSIONS_MATRIX = {
        "Super Admin": {
            "description": "Full unconstrained administrative privileges across all system domains and configurations.",
            "is_system_role": True,
            "permissions": {
                ModuleChoice.INFLUENCERS: AccessLevel.FULL,
                ModuleChoice.BUSINESSES: AccessLevel.FULL,
                ModuleChoice.CAMPAIGNS: AccessLevel.FULL,
                ModuleChoice.REQUIREMENTS: AccessLevel.FULL,
                ModuleChoice.WEBSITES: AccessLevel.FULL,
                ModuleChoice.DOMAINS: AccessLevel.FULL,
                ModuleChoice.SOCIAL_PLATFORMS: AccessLevel.FULL,
                ModuleChoice.PAYMENTS: AccessLevel.FULL,
                ModuleChoice.SUBSCRIPTIONS: AccessLevel.FULL,
                ModuleChoice.SUPPORT: AccessLevel.FULL,
                ModuleChoice.AUDIT_LOGS: AccessLevel.FULL,
                ModuleChoice.SETTINGS: AccessLevel.FULL,
                ModuleChoice.TAXONOMIES: AccessLevel.FULL,
                ModuleChoice.MEDIA: AccessLevel.FULL,
            }
        },
        "Admin": {
            "description": "Operations manager with full management over accounts, content, marketplace, and operational queues.",
            "is_system_role": True,
            "permissions": {
                ModuleChoice.INFLUENCERS: AccessLevel.MANAGE,
                ModuleChoice.BUSINESSES: AccessLevel.MANAGE,
                ModuleChoice.CAMPAIGNS: AccessLevel.MANAGE,
                ModuleChoice.REQUIREMENTS: AccessLevel.MANAGE,
                ModuleChoice.WEBSITES: AccessLevel.MANAGE,
                ModuleChoice.DOMAINS: AccessLevel.MANAGE,
                ModuleChoice.SOCIAL_PLATFORMS: AccessLevel.MANAGE,
                ModuleChoice.PAYMENTS: AccessLevel.VIEW,
                ModuleChoice.SUBSCRIPTIONS: AccessLevel.MANAGE,
                ModuleChoice.SUPPORT: AccessLevel.MANAGE,
                ModuleChoice.AUDIT_LOGS: AccessLevel.VIEW,
                ModuleChoice.SETTINGS: AccessLevel.LIMITED,
                ModuleChoice.TAXONOMIES: AccessLevel.MANAGE,
                ModuleChoice.MEDIA: AccessLevel.MANAGE,
            }
        },
        "Moderator": {
            "description": "Content and safety moderator reviewing verification badges, creator media, and brand marketplace campaigns.",
            "is_system_role": True,
            "permissions": {
                ModuleChoice.INFLUENCERS: AccessLevel.VIEW,
                ModuleChoice.BUSINESSES: AccessLevel.VIEW,
                ModuleChoice.CAMPAIGNS: AccessLevel.MODERATE,
                ModuleChoice.REQUIREMENTS: AccessLevel.MODERATE,
                ModuleChoice.WEBSITES: AccessLevel.MODERATE,
                ModuleChoice.DOMAINS: AccessLevel.NONE,
                ModuleChoice.SOCIAL_PLATFORMS: AccessLevel.VIEW,
                ModuleChoice.PAYMENTS: AccessLevel.NONE,
                ModuleChoice.SUBSCRIPTIONS: AccessLevel.NONE,
                ModuleChoice.SUPPORT: AccessLevel.VIEW,
                ModuleChoice.AUDIT_LOGS: AccessLevel.NONE,
                ModuleChoice.SETTINGS: AccessLevel.NONE,
                ModuleChoice.TAXONOMIES: AccessLevel.VIEW,
                ModuleChoice.MEDIA: AccessLevel.MODERATE,
            }
        },
        "Support": {
            "description": "Customer support representative triaging tickets, inspecting account states, and helping creators/brands.",
            "is_system_role": True,
            "permissions": {
                ModuleChoice.INFLUENCERS: AccessLevel.VIEW,
                ModuleChoice.BUSINESSES: AccessLevel.VIEW,
                ModuleChoice.CAMPAIGNS: AccessLevel.VIEW,
                ModuleChoice.REQUIREMENTS: AccessLevel.VIEW,
                ModuleChoice.WEBSITES: AccessLevel.VIEW,
                ModuleChoice.DOMAINS: AccessLevel.VIEW,
                ModuleChoice.SOCIAL_PLATFORMS: AccessLevel.NONE,
                ModuleChoice.PAYMENTS: AccessLevel.NONE,
                ModuleChoice.SUBSCRIPTIONS: AccessLevel.VIEW,
                ModuleChoice.SUPPORT: AccessLevel.FULL,
                ModuleChoice.AUDIT_LOGS: AccessLevel.NONE,
                ModuleChoice.SETTINGS: AccessLevel.NONE,
                ModuleChoice.TAXONOMIES: AccessLevel.NONE,
                ModuleChoice.MEDIA: AccessLevel.VIEW,
            }
        },
        "Finance": {
            "description": "Financial controller managing payments, transactions, billing plans, and revenue analytics.",
            "is_system_role": True,
            "permissions": {
                ModuleChoice.INFLUENCERS: AccessLevel.NONE,
                ModuleChoice.BUSINESSES: AccessLevel.VIEW,
                ModuleChoice.CAMPAIGNS: AccessLevel.NONE,
                ModuleChoice.REQUIREMENTS: AccessLevel.NONE,
                ModuleChoice.WEBSITES: AccessLevel.NONE,
                ModuleChoice.DOMAINS: AccessLevel.NONE,
                ModuleChoice.SOCIAL_PLATFORMS: AccessLevel.NONE,
                ModuleChoice.PAYMENTS: AccessLevel.FULL,
                ModuleChoice.SUBSCRIPTIONS: AccessLevel.MANAGE,
                ModuleChoice.SUPPORT: AccessLevel.NONE,
                ModuleChoice.AUDIT_LOGS: AccessLevel.VIEW,
                ModuleChoice.SETTINGS: AccessLevel.NONE,
                ModuleChoice.TAXONOMIES: AccessLevel.NONE,
                ModuleChoice.MEDIA: AccessLevel.NONE,
            }
        },
        "Content Manager": {
            "description": "Editorial and platform curator managing website templates, social platforms, taxonomies, and creators.",
            "is_system_role": True,
            "permissions": {
                ModuleChoice.INFLUENCERS: AccessLevel.MANAGE,
                ModuleChoice.BUSINESSES: AccessLevel.NONE,
                ModuleChoice.CAMPAIGNS: AccessLevel.MODERATE,
                ModuleChoice.REQUIREMENTS: AccessLevel.MODERATE,
                ModuleChoice.WEBSITES: AccessLevel.MANAGE,
                ModuleChoice.DOMAINS: AccessLevel.NONE,
                ModuleChoice.SOCIAL_PLATFORMS: AccessLevel.MANAGE,
                ModuleChoice.PAYMENTS: AccessLevel.NONE,
                ModuleChoice.SUBSCRIPTIONS: AccessLevel.NONE,
                ModuleChoice.SUPPORT: AccessLevel.NONE,
                ModuleChoice.AUDIT_LOGS: AccessLevel.NONE,
                ModuleChoice.SETTINGS: AccessLevel.LIMITED,
                ModuleChoice.TAXONOMIES: AccessLevel.MANAGE,
                ModuleChoice.MEDIA: AccessLevel.MANAGE,
            }
        },
    }

    def handle(self, *args, **options) -> None:
        """
        Execute seeding logic inside an isolated atomic database transaction.
        
        :param args: Additional positional arguments from command invocation.
        :param options: Command options and flags.
        :return: None
        """
        self.stdout.write(self.style.NOTICE("Beginning RBAC role templates and permissions synchronization..."))

        total_roles_created = 0
        total_roles_updated = 0
        total_permissions_synced = 0

        # Step 1: Wrap entire seeding workflow in an atomic transaction
        with transaction.atomic():
            for role_name, data in self.ROLE_PERMISSIONS_MATRIX.items():
                # Step 2: Upsert the RoleTemplate record
                role_template, created = RoleTemplate.objects.update_or_create(
                    name=role_name,
                    defaults={
                        "description": data["description"],
                        "is_system_role": data["is_system_role"],
                        "is_deleted": False,
                    }
                )

                if created:
                    total_roles_created += 1
                    self.stdout.write(self.style.SUCCESS(f"  [+] Created RoleTemplate: '{role_name}'"))
                else:
                    total_roles_updated += 1
                    self.stdout.write(f"  [*] Updated RoleTemplate: '{role_name}'")

                # Step 3: Upsert the 14 module permissions for this role
                for module_choice, access_tier in data["permissions"].items():
                    RolePermission.objects.update_or_create(
                        role_template=role_template,
                        module=module_choice,
                        defaults={
                            "access_level": access_tier,
                            "is_deleted": False,
                        }
                    )
                    total_permissions_synced += 1

        # Step 4: Output summary metrics
        self.stdout.write(self.style.SUCCESS(
            f"\nRBAC seeding completed successfully:\n"
            f"  - Roles Created: {total_roles_created}\n"
            f"  - Roles Updated: {total_roles_updated}\n"
            f"  - Permissions Synced: {total_permissions_synced} across 14 operational modules."
        ))
