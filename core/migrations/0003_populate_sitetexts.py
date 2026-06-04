from django.db import migrations


def create_default_site_texts(apps, schema_editor):
    SiteText = apps.get_model('core', 'SiteText')
    defaults = {
        'marquee_text': 'ENVÍOS GRATIS A TODO EL PAÍS · 3 Y 6 CUOTAS SIN INTERÉS · HASTA 70% OFF · NUEVA COLECCIÓN ·',
        'hero_eyebrow': 'SOLO POR 3 DÍAS',
        'hero_headline': 'HOT <em>BY Josephine</em>',
        'hero_badge_1': 'Hasta 70% OFF',
        'hero_badge_2': '+ Envíos gratis',
    }
    for key, text in defaults.items():
        SiteText.objects.update_or_create(key=key, defaults={'text': text, 'description': ''})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_sitetext'),
    ]

    operations = [
        migrations.RunPython(create_default_site_texts, reverse_code=migrations.RunPython.noop),
    ]
