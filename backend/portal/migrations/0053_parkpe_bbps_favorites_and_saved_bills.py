# ParkPe BBPS: favorites and saved bills in DB (sync across devices)

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0052_partner_vendor_assignment_lookup_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParkPeBBPSFavoriteBiller',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operator_id', models.CharField(db_index=True, max_length=128)),
                ('operator_name', models.CharField(default='', max_length=255)),
                ('category', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='parkpe_bbps_favorites', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ParkPe BBPS Favorite Biller',
                'verbose_name_plural': 'ParkPe BBPS Favorite Billers',
                'db_table': 'portal_parkpe_bbps_favorite_biller',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ParkPeBBPSSavedBill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nickname', models.CharField(blank=True, default='', max_length=128)),
                ('operator_id', models.CharField(db_index=True, max_length=128)),
                ('operator_name', models.CharField(default='', max_length=255)),
                ('category', models.CharField(blank=True, default='', max_length=64)),
                ('consumer_id', models.CharField(max_length=255)),
                ('last_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Last known bill amount', max_digits=14, null=True)),
                ('bill_id', models.CharField(blank=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='parkpe_bbps_saved_bills', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'ParkPe BBPS Saved Bill',
                'verbose_name_plural': 'ParkPe BBPS Saved Bills',
                'db_table': 'portal_parkpe_bbps_saved_bill',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='parkpebbpsfavoritebiller',
            constraint=models.UniqueConstraint(fields=('user', 'operator_id'), name='parkpe_bbps_fav_user_operator_unique'),
        ),
    ]
