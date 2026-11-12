from django.db import migrations


def seed_default_plans(apps, schema_editor):
    Plan = apps.get_model('billing', 'Plan')
    
    default_plans = [
        {
            'name': 'Free',
            'audience': 'BUSINESS',
            'price_cents': 0,
            'currency': 'INR',
            'interval': 'MONTHLY',
            'features_list': [
                'Basic creator discovery',
                '2 shortlists',
                '10 inquiries per month',
                '1 active requirement',
                'Community support'
            ],
            'is_active': True
        },
        {
            'name': 'Business Pro',
            'audience': 'BUSINESS',
            'price_cents': 299900,  # 2,999.00 INR
            'currency': 'INR',
            'interval': 'MONTHLY',
            'features_list': [
                'Advanced filters & saved searches',
                'Unlimited shortlists',
                '500 inquiries per month',
                'Full campaign management',
                'Content approval workflow',
                'Performance analytics'
            ],
            'is_active': True
        },
        {
            'name': 'Agency',
            'audience': 'BUSINESS',
            'price_cents': 999900,  # 9,999.00 INR
            'currency': 'INR',
            'interval': 'MONTHLY',
            'features_list': [
                'Everything in Business Pro',
                'Up to 10 team members',
                'Unlimited client workspaces',
                'Advanced campaign automation',
                'White-label reporting',
                'Dedicated account manager'
            ],
            'is_active': True
        },
        {
            'name': 'Free Creator',
            'audience': 'INFLUENCER',
            'price_cents': 0,
            'currency': 'INR',
            'interval': 'MONTHLY',
            'features_list': [
                'Portfolio website',
                'Basic rate cards',
                'Direct brand inquiries'
            ],
            'is_active': True
        },
        {
            'name': 'Pro Creator',
            'audience': 'INFLUENCER',
            'price_cents': 99900,  # 999.00 INR
            'currency': 'INR',
            'interval': 'MONTHLY',
            'features_list': [
                'Custom domain connection',
                'Verified creator badge',
                'Exportable branded Media Kit PDF',
                'Priority marketplace listing',
                'Advanced performance analytics'
            ],
            'is_active': True
        }
    ]

    for p in default_plans:
        Plan.objects.get_or_create(
            name=p['name'],
            audience=p['audience'],
            defaults=p
        )


def rollback_default_plans(apps, schema_editor):
    Plan = apps.get_model('billing', 'Plan')
    Plan.objects.filter(name__in=['Free', 'Business Pro', 'Agency', 'Free Creator', 'Pro Creator']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_plans, rollback_default_plans),
    ]

