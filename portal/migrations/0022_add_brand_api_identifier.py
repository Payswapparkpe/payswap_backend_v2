# Generated migration: 6-char alphanumeric api_identifier for GiftVoucherBrand

import random
import string
from django.db import migrations, models


def generate_api_identifier():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.SystemRandom().choice(chars) for _ in range(6))


def backfill_api_identifiers(apps, schema_editor):
    GiftVoucherBrand = apps.get_model('portal', 'GiftVoucherBrand')
    for brand in GiftVoucherBrand.objects.all():
        if brand.api_identifier:
            continue
        for _ in range(100):
            code = generate_api_identifier()
            if not GiftVoucherBrand.objects.filter(api_identifier=code).exists():
                brand.api_identifier = code
                brand.save(update_fields=['api_identifier'])
                break
        else:
            raise ValueError(f"Could not generate unique api_identifier for brand {brand.id}")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0021_add_view_voucher_sensitive_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='giftvoucherbrand',
            name='api_identifier',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='6-char alphanumeric unique code for API; brand isi code se identify hota hai. Auto-generate on save.',
                max_length=6,
                null=True,
                unique=True
            ),
        ),
        migrations.RunPython(backfill_api_identifiers, noop),
    ]
