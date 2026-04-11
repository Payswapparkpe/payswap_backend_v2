# Generated migration: PIN / session lock fields on User (soft-lock re-unlock)
# PIN is secondary unlock only; OTP/2FA remains primary authentication.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0027_add_balance_non_negative_constraints'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='pin_hash',
            field=models.CharField(blank=True, help_text='Hashed 4-digit PIN (Django make_password). Never store plaintext.', max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='pin_set_at',
            field=models.DateTimeField(blank=True, help_text='When PIN was last set', null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='pin_failed_attempts',
            field=models.IntegerField(default=0, help_text='Consecutive failed PIN attempts; lock after 5'),
        ),
        migrations.AddField(
            model_name='user',
            name='pin_locked_until',
            field=models.DateTimeField(blank=True, help_text='PIN unlock blocked until this time (30 min after 5 failures)', null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='last_full_auth_at',
            field=models.DateTimeField(blank=True, help_text='Last successful OTP/2FA login; PIN unlock allowed only within window (e.g. 24h)', null=True),
        ),
    ]
