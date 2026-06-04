from django.db import migrations, models


def blank_codes_to_null(apps, schema_editor):
    Promotion = apps.get_model('promotions', 'Promotion')
    Promotion.objects.filter(code='').update(code=None)


class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0002_promotion_is_deleted'),
    ]

    operations = [
        migrations.AlterField(
            model_name='promotion',
            name='code',
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True, unique=True),
        ),
        migrations.RunPython(blank_codes_to_null, reverse_code=migrations.RunPython.noop),
    ]
