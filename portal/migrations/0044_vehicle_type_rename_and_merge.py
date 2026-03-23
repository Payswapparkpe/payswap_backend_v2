# Vehicle type: 2 Wheeler -> Bike/Scooty, 4 Wheeler -> Private Car;
# 3 Wheeler merged into Commercial. Migrate existing three_wheeler to commercial.

from django.db import migrations


def three_wheeler_to_commercial(apps, schema_editor):
    Vehicle = apps.get_model('portal', 'Vehicle')
    Vehicle.objects.filter(vehicle_type='three_wheeler').update(vehicle_type='commercial')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0043_vehicle_vehicle_type'),
    ]

    operations = [
        migrations.RunPython(three_wheeler_to_commercial, noop),
    ]
