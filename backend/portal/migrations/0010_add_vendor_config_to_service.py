# Generated manually for vendor_config field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0009_alter_logentry_category_cashfreeapilog'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='vendor_config',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Vendor service configurations - stores which services are enabled/disabled per vendor'
            ),
        ),
    ]
