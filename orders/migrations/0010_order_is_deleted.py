from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_alter_order_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]
