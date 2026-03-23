from django.db import migrations, models


def backfill_vehicle_normalized_registration(apps, schema_editor):
    Vehicle = apps.get_model("portal", "Vehicle")
    for vehicle in Vehicle.objects.all().only("id", "registration_number"):
        normalized = "".join((vehicle.registration_number or "").strip().upper().split())
        Vehicle.objects.filter(pk=vehicle.pk).update(registration_number_normalized=normalized)


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0059_add_hub_income_record"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="registration_number_normalized",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Uppercased registration without spaces for indexed lookups",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="connectthread",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, db_index=True, null=True),
        ),
        migrations.RunPython(backfill_vehicle_normalized_registration, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name="connectthread",
            options={
                "db_table": "portal_connect_thread",
                "ordering": ["-updated_at"],
                "verbose_name": "Connect Thread",
                "verbose_name_plural": "Connect Threads",
            },
        ),
        migrations.AlterField(
            model_name="connectthread",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterField(
            model_name="connectthread",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, db_index=True),
        ),
    ]
