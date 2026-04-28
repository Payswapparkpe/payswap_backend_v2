from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rbac", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userhubassignment",
            name="expires_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="Optional: auto-deactivate after this datetime. Leave blank for permanent access.",
                null=True,
            ),
        ),
    ]
