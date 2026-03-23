# Step 4: Index for get_partner_vendor lookup at v2 scale (1M users)
# Query: filter(partner=, service_code=, is_active=True, is_primary=True).first()

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0051_connectscanlog'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='partnervendorassignment',
            index=models.Index(
                fields=['partner', 'service_code', 'is_active', 'is_primary'],
                name='pva_partner_svc_active_primary',
            ),
        ),
    ]
