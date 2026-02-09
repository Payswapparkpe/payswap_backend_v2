# Generated migration: Vendor-orchestrated service flow (ApiVendor, VendorApi, ServiceFlowStep)
# Backward-compatible: existing Service unchanged except optional category field

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0029_add_email_queue'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='category',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Service category for orchestration (AEPS, DMT, BBPS, etc.)',
                max_length=50,
                null=True
            ),
        ),
        migrations.CreateModel(
            name='ApiVendor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Vendor name (e.g. PayPoint, Euronet)', max_length=100)),
                ('code', models.CharField(db_index=True, help_text='Unique slug (e.g. paypoint, euronet)', max_length=50, unique=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'API Vendor',
                'verbose_name_plural': 'API Vendors',
                'db_table': 'portal_apivendor',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='VendorApi',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='e.g. Add Agent, AEPS Balance Enquiry', max_length=150)),
                ('api_code', models.CharField(help_text='Unique per vendor (e.g. add_agent, balance_enquiry)', max_length=80)),
                ('api_type', models.CharField(choices=[('SETUP', 'Setup'), ('VALIDATION', 'Validation'), ('AUTH', 'Authentication'), ('TRANSACTION', 'Transaction'), ('2FA', 'Two Factor Auth'), ('QUERY', 'Query')], db_index=True, default='TRANSACTION', max_length=20)),
                ('endpoint_url', models.URLField(blank=True, help_text='Optional; actual call may be via registered handler', null=True)),
                ('http_method', models.CharField(blank=True, default='POST', max_length=10)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('timeout_seconds', models.PositiveIntegerField(blank=True, default=30)),
                ('retry_allowed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='apis', to='portal.apivendor')),
            ],
            options={
                'verbose_name': 'Vendor API',
                'verbose_name_plural': 'Vendor APIs',
                'db_table': 'portal_vendorapi',
                'ordering': ['vendor', 'api_code'],
                'unique_together': {('vendor', 'api_code')},
            },
        ),
        migrations.CreateModel(
            name='ServiceFlowStep',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('step_order', models.PositiveIntegerField(help_text='Execution order; unique per service')),
                ('step_name', models.CharField(help_text='Display name (e.g. Add Agent, Check Authentication)', max_length=150)),
                ('is_mandatory', models.BooleanField(default=True)),
                ('halt_on_failure', models.BooleanField(default=True, help_text='Stop flow if this step fails')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flow_steps', to='portal.service')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='flow_steps', to='portal.apivendor')),
                ('vendor_api', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='flow_steps', to='portal.vendorapi')),
            ],
            options={
                'verbose_name': 'Service Flow Step',
                'verbose_name_plural': 'Service Flow Steps',
                'db_table': 'portal_serviceflowstep',
                'ordering': ['service', 'step_order'],
                'unique_together': {('service', 'step_order')},
            },
        ),
    ]
