from django.db import migrations


def create_product_badges(apps, schema_editor):
    SiteText = apps.get_model('core', 'SiteText')
    defaults = {
        'product_badge_new_in': 'NUEVO IN',
        'product_badge_hot_sale': 'HOT SALE',
    }
    for key, text in defaults.items():
        SiteText.objects.update_or_create(key=key, defaults={'text': text, 'description': ''})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_footer_texts'),
    ]

    operations = [
        migrations.RunPython(create_product_badges, reverse_code=migrations.RunPython.noop),
    ]
