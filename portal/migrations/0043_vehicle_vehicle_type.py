# Generated migration for ParkPe Connect vehicle type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0042_vehicle_rc_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='vehicle_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', ''),
                    ('two_wheeler', '2 Wheeler'),
                    ('three_wheeler', '3 Wheeler'),
                    ('four_wheeler', '4 Wheeler'),
                    ('commercial', 'Commercial'),
                ],
                db_index=True,
                default='',
                help_text='2 Wheeler, 3 Wheeler, 4 Wheeler, or Commercial',
                max_length=20,
            ),
        ),
    ]
