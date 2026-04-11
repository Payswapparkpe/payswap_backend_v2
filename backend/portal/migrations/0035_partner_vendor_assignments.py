# Partner Vendor Assignment and Internal API Key models
# Extends ResellerPartnerPricing with optional vendor-specific pricing

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0034_add_profile_postman_api_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartnerVendorAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_code', models.CharField(db_index=True, help_text='Service code: bbps, aeps, dmt, kyc, sms, payment, voucher', max_length=50)),
                ('is_primary', models.BooleanField(default=True, help_text='Primary vendor for this service (used when no vendor specified)')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('priority', models.IntegerField(default=1, help_text='Order for fallback routing (lower = higher priority)')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('assigned_by', models.ForeignKey(blank=True, help_text='Admin who made the assignment', null=True, on_delete=models.deletion.SET_NULL, related_name='assigned_partner_vendors', to=settings.AUTH_USER_MODEL)),
                ('partner', models.ForeignKey(help_text='Reseller partner', on_delete=models.deletion.CASCADE, related_name='vendor_assignments', to='portal.resellerpartner')),
                ('vendor', models.ForeignKey(help_text='API vendor assigned for this service', on_delete=models.deletion.CASCADE, related_name='partner_assignments', to='portal.apivendor')),
            ],
            options={
                'verbose_name': 'Partner Vendor Assignment',
                'verbose_name_plural': 'Partner Vendor Assignments',
                'db_table': 'portal_partner_vendor_assignment',
                'ordering': ['service_code', 'priority'],
            },
        ),
        migrations.CreateModel(
            name='InternalAPIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('app_name', models.CharField(db_index=True, help_text='App identifier: payswap, parkpe', max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('environment', models.CharField(default='production', help_text='development, staging, production', max_length=20)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('api_key', models.ForeignKey(help_text='API key used by this app', on_delete=models.deletion.CASCADE, related_name='internal_app_bindings', to='portal.apikey')),
                ('updated_by', models.ForeignKey(blank=True, help_text='User who last updated this record', null=True, on_delete=models.deletion.SET_NULL, related_name='updated_internal_api_keys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Internal API Key',
                'verbose_name_plural': 'Internal API Keys',
                'db_table': 'portal_internal_api_key',
                'ordering': ['app_name'],
            },
        ),
        migrations.AddField(
            model_name='resellerpartnerpricing',
            name='vendor',
            field=models.ForeignKey(blank=True, help_text='Vendor-specific pricing (null = default for service)', null=True, on_delete=models.deletion.CASCADE, related_name='partner_pricing', to='portal.apivendor'),
        ),
        migrations.AlterUniqueTogether(
            name='resellerpartnerpricing',
            unique_together={('partner', 'service', 'vendor')},
        ),
        migrations.AddIndex(
            model_name='resellerpartnerpricing',
            index=models.Index(fields=['partner', 'service', 'vendor'], name='portal_res_partner_servic_idx'),
        ),
        migrations.AddConstraint(
            model_name='resellerpartnerpricing',
            constraint=models.UniqueConstraint(condition=Q(vendor__isnull=True), fields=('partner', 'service'), name='portal_reseller_partner_pricing_unique_default'),
        ),
    ]
