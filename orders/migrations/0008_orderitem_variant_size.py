from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_productreservation_locked_by_order_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='variant_size',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]