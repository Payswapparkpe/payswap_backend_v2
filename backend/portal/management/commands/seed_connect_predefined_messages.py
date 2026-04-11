"""
Seed default Connect chat predefined messages (wrong parking, wrong driving, please move, etc.).
Creates records if they do not exist; does not overwrite existing ones.
"""
from django.core.management.base import BaseCommand

from portal.models import ConnectPredefinedMessage


DEFAULTS = [
    {
        "code": "wrong_parking",
        "label_en": "Wrong parking",
        "label_hi": "गलत पार्किंग",
        "body_en": "Your vehicle is parked incorrectly. Please move it.",
        "body_hi": "आपकी गाड़ी गलत जगह खड़ी है। कृपया इसे हटाएं।",
        "order": 10,
    },
    {
        "code": "wrong_driving",
        "label_en": "You're driving incorrectly",
        "label_hi": "गलत तरीके से गाड़ी चला रहे हैं",
        "body_en": "You are driving incorrectly. Please follow traffic rules.",
        "body_hi": "आप गलत तरीके से गाड़ी चला रहे हैं। कृपया यातायात नियमों का पालन करें।",
        "order": 20,
    },
    {
        "code": "please_move_vehicle",
        "label_en": "Please move your vehicle",
        "label_hi": "कृपया अपनी गाड़ी हटाएं",
        "body_en": "Please move your vehicle from this spot.",
        "body_hi": "कृपया अपनी गाड़ी इस जगह से हटाएं।",
        "order": 30,
    },
    {
        "code": "blocking_exit",
        "label_en": "Blocking exit",
        "label_hi": "निकास रुका हुआ",
        "body_en": "Your vehicle is blocking the exit. Please move it.",
        "body_hi": "आपकी गाड़ी निकास को रोक रही है। कृपया इसे हटाएं।",
        "order": 40,
    },
    {
        "code": "lights_on",
        "label_en": "Lights left on",
        "label_hi": "लाइटें चालू छोड़ी",
        "body_en": "Your vehicle lights are still on. You may want to turn them off.",
        "body_hi": "आपकी गाड़ी की लाइटें अभी भी चालू हैं। कृपया बंद करें।",
        "order": 50,
    },
]


class Command(BaseCommand):
    help = "Seed default Connect predefined chat messages (wrong_parking, wrong_driving, etc.)."

    def handle(self, *args, **options):
        created = 0
        for item in DEFAULTS:
            obj, was_created = ConnectPredefinedMessage.objects.get_or_create(
                code=item["code"],
                defaults={
                    "label_en": item["label_en"],
                    "label_hi": item.get("label_hi", ""),
                    "body_en": item["body_en"],
                    "body_hi": item.get("body_hi", ""),
                    "is_active": True,
                    "order": item["order"],
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created: {obj.code}"))
        if created == 0:
            self.stdout.write("All predefined messages already exist.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Created {created} predefined message(s)."))
