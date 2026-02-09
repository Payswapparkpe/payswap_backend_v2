# Durable email queue: source of truth for outbound emails. Survives Celery failure.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0028_add_user_pin_lock_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailQueue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('to_email', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=512)),
                ('body_html', models.TextField(blank=True, null=True)),
                ('body_text', models.TextField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('PENDING', 'Pending'), ('SENT', 'Sent'), ('FAILED', 'Failed')],
                    db_index=True,
                    default='PENDING',
                    max_length=20,
                )),
                ('retry_count', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, null=True)),
                ('related_entity', models.JSONField(blank=True, null=True)),
                ('use_parkpe_smtp', models.BooleanField(default=False, help_text='Use Parkpe SMTP (voucher emails)')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Email Queue',
                'verbose_name_plural': 'Email Queue',
                'db_table': 'portal_email_queue',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emailqueue',
            index=models.Index(fields=['status', 'created_at'], name='portal_emai_status_8a0b0d_idx'),
        ),
    ]
