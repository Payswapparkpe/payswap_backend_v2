import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ParkingLocation, ParkingSlot, BookingRequest, Booking } from '../../../core/models/parking.model';

@Injectable({
  providedIn: 'root',
})
export class ParkingService {
  private api = inject(API_BACKEND_TOKEN);

  getLocations(): Observable<ParkingLocation[]> {
    return this.api.getLocations();
  }

  getSlots(locationId: string): Observable<ParkingSlot[]> {
    return this.api.getSlots(locationId);
  }

  createBooking(payload: BookingRequest): Observable<Booking> {
    return this.api.createBooking(payload);
  }

  getBooking(id: string): Observable<Booking> {
    return this.api.getBooking(id);
  }
}
