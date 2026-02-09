# Generated manually for Postman sync

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0033_add_vendorapi_purpose'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='postman_api_key',
            field=models.CharField(blank=True, help_text='Postman API key for syncing collections to this portal (optional)', max_length=255, null=True),
        ),
    ]
