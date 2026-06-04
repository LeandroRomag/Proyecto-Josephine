from django.db import migrations


def create_footer_texts(apps, schema_editor):
    SiteText = apps.get_model('core', 'SiteText')
    defaults = {
        'footer_help_envois': 'Envíos y devoluciones',
        'footer_help_talles': 'Guía de talles',
    }
    for key, text in defaults.items():
        SiteText.objects.update_or_create(key=key, defaults={'text': text, 'description': ''})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_populate_sitetexts'),
    ]

    operations = [
        migrations.RunPython(create_footer_texts, reverse_code=migrations.RunPython.noop),
    ]
