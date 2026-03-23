from celery import shared_task


@shared_task(name="portal.tasks.fetch_connect_vehicle_rc", bind=True, max_retries=3)
def fetch_connect_vehicle_rc_task(self, vehicle_id: int):
    from portal.models import Vehicle, VehicleRCData
    from portal.services.cashfree_vehicle_rc import fetch_vehicle_rc

    try:
        vehicle = Vehicle.objects.filter(pk=vehicle_id).only("id", "registration_number").first()
        if not vehicle:
            return {"status": "skipped", "reason": "vehicle_not_found"}

        reg = (vehicle.registration_number or "").strip().upper()
        if not reg:
            return {"status": "skipped", "reason": "registration_missing"}

        rc_response, _, _ = fetch_vehicle_rc(reg)
        if not rc_response:
            return {"status": "no_data"}

        VehicleRCData.objects.update_or_create(
            vehicle_id=vehicle.pk,
            defaults={"raw_response": rc_response},
        )
        return {"status": "success", "vehicle_id": vehicle.pk}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)
