import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ParkingLocation, ParkingSlot, BookingRequest, Booking } from '../../../core/models/parking.model';

@Injectable({
  providedIn: 'root',
})
export class ParkingService {
  private api = inject(API_BACKEND_TOKEN);

  getLocations(params?: { lat?: number; lng?: number; radius_km?: number; city?: string }): Observable<ParkingLocation[]> {
    return (this.api as any).getLocations(params);
  }

  getSlots(locationId: string, vehicleType?: string): Observable<ParkingSlot[]> {
    return (this.api as any).getSlots(locationId, vehicleType);
  }

  getRateEstimate(locationId: string, vehicleType: string, durationHours: number): Observable<any> {
    return (this.api as any).getParkingRateEstimate(locationId, vehicleType, durationHours);
  }

  createBooking(payload: BookingRequest): Observable<Booking> {
    return this.api.createBooking(payload);
  }

  getBooking(id: string): Observable<Booking> {
    return this.api.getBooking(id);
  }

  cancelBooking(bookingRef: string, reason?: string): Observable<any> {
    return (this.api as any).cancelBooking(bookingRef, reason);
  }

  recordEntry(bookingRef: string, qrPayload?: string): Observable<any> {
    return (this.api as any).recordParkingEntry(bookingRef, qrPayload);
  }

  recordExit(bookingRef: string): Observable<any> {
    return (this.api as any).recordParkingExit(bookingRef);
  }

  resendTicket(bookingRef: string): Observable<any> {
    return (this.api as any).resendParkingTicket(bookingRef);
  }

  getHistory(page = 1, pageSize = 20): Observable<{ bookings: Booking[]; total: number }> {
    return (this.api as any).getParkingHistory(page, pageSize);
  }

  getOwnerRevenue(locationId: string, days = 30): Observable<any> {
    return (this.api as any).getParkingOwnerRevenue(locationId, days);
  }
}
