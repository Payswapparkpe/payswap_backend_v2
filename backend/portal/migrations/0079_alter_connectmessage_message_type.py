from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0078_connect_chat_mvp_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="connectmessage",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("predefined", "Predefined"),
                    ("attachment", "Attachment"),
                    ("voice", "Voice"),
                ],
                db_index=True,
                default="text",
                max_length=20,
            ),
        ),
    ]
