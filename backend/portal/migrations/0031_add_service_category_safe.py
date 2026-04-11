# Safe fix: add portal_service.category if missing (e.g. DB restored or 0030 partially applied)
# Uses raw SQL so it no-ops when column already exists.

from django.db import migrations


def add_category_if_missing(apps, schema_editor):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'portal_service' AND column_name = 'category'
        """)
        if cursor.fetchone():
            return
        cursor.execute("""
            ALTER TABLE portal_service
            ADD COLUMN category VARCHAR(50) NULL;
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS portal_service_category_idx
            ON portal_service (category);
        """)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0030_add_vendor_flow_models'),
    ]

    operations = [
        migrations.RunPython(add_category_if_missing, noop_reverse),
    ]
