import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ApiBackend } from '../../../core/api/api-backend.interface';
import {
  ParkingLocation,
  ParkingSlot,
  BookingRequest,
  Booking,
  ParkingExitPreview,
  ParkingExitUpiOrder,
  ParkingExitPaymentStatus,
  VehicleFastagMapping,
} from '../../../core/models/parking.model';

@Injectable({
  providedIn: 'root',
})
export class ParkingService {
  private api = inject(API_BACKEND_TOKEN) as ApiBackend;

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

  getExitPreview(bookingRef: string): Observable<ParkingExitPreview> {
    return this.api.getParkingExitPreview(bookingRef);
  }

  payExitVoucher(bookingRef: string, pin: string): Observable<Record<string, unknown>> {
    return this.api.payParkingExitVoucher(bookingRef, pin);
  }

  payExitUpi(bookingRef: string): Observable<ParkingExitUpiOrder> {
    return this.api.payParkingExitUpi(bookingRef);
  }

  pollExitPaymentStatus(exitPaymentId: number): Observable<ParkingExitPaymentStatus> {
    return this.api.getParkingExitPaymentStatus(exitPaymentId);
  }

  getFastagMappings(): Observable<{ mappings: VehicleFastagMapping[] }> {
    return this.api.getParkingFastagMappings();
  }

  linkFastag(body: {
    vehicleNumber: string;
    fastagId: string;
    issuer?: string;
    fastagWalletId?: string;
  }): Observable<{ success: boolean; mapping: VehicleFastagMapping }> {
    return this.api.linkParkingFastag(body);
  }

  getOwnerRevenue(locationId: string, days = 30): Observable<any> {
    return (this.api as any).getParkingOwnerRevenue(locationId, days);
  }

  getOwnerLocations(): Observable<any> {
    return (this.api as any).getParkingOwnerLocations();
  }

  getOwnerProfile(): Observable<any> {
    return (this.api as any).getParkingOwnerProfile();
  }

  getOwnerBookings(locationId: string, date?: string, status?: string): Observable<any> {
    return (this.api as any).getParkingOwnerBookings(locationId, date, status);
  }

  getLocationSlots(locationId: string): Observable<ParkingSlot[]> {
    return (this.api as any).getSlots(locationId);
  }

  getOwnerTeam(locationId: string): Observable<any> {
    return (this.api as any).getParkingOwnerTeam(locationId);
  }

  createOwnerTeamUser(locationId: string, payload: { email?: string; username?: string; role: string; notes?: string }): Observable<any> {
    return (this.api as any).createParkingOwnerTeamUser(locationId, payload);
  }

  updateOwnerTeamUser(locationId: string, operatorId: number, payload: { role?: string; isActive?: boolean; notes?: string }): Observable<any> {
    return (this.api as any).updateParkingOwnerTeamUser(locationId, operatorId, payload);
  }

  deactivateOwnerTeamUser(locationId: string, operatorId: number): Observable<any> {
    return (this.api as any).deactivateParkingOwnerTeamUser(locationId, operatorId);
  }
}
