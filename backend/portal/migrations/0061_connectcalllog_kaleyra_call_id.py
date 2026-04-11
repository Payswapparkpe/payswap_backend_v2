from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0060_connect_vehicle_lookup_and_thread_timestamps"),
    ]

    operations = [
        migrations.AddField(
            model_name="connectcalllog",
            name="kaleyra_call_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Call ID returned by Kaleyra click-to-call API for cross-referencing with vendor logs",
                max_length=128,
            ),
        ),
    ]
