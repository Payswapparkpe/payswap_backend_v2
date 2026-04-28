from django.db import migrations


def seed_parking_roles(apps, schema_editor):
    Role = apps.get_model("portal", "Role")
    roles_data = [
        {
            "name": "Parking Owner",
            "code": "parking_owner",
            "category": "b2b",
            "hierarchy_level": 35,
            "mfa_required": False,
        },
        {
            "name": "Parking Manager",
            "code": "parking_manager",
            "category": "b2b",
            "hierarchy_level": 32,
            "mfa_required": False,
        },
        {
            "name": "Parking Attendant",
            "code": "parking_attendant",
            "category": "b2b",
            "hierarchy_level": 28,
            "mfa_required": False,
        },
    ]
    for role_data in roles_data:
        Role.objects.update_or_create(
            code=role_data["code"],
            defaults=role_data,
        )


def unseed_parking_roles(apps, schema_editor):
    Role = apps.get_model("portal", "Role")
    Role.objects.filter(
        code__in=["parking_owner", "parking_manager", "parking_attendant"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0087_parking_models"),
    ]

    operations = [
        migrations.RunPython(seed_parking_roles, unseed_parking_roles),
    ]

