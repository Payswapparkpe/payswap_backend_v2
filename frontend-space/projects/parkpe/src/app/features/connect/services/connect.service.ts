import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface ConnectVehicle {
  id: number;
  registration_number: string;
  brand: string;
  model: string;
  year: number | null;
  photo: string | null;
  is_primary: boolean;
  qr_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectVehicleCreate {
  registration_number: string;
  brand?: string;
  model?: string;
  year?: number | null;
  photo?: string | null;
  is_primary?: boolean;
}

export interface VehicleByQRResponse {
  vehicle_id: number;
  qr_code: string;
  registration_number_masked: string;
  brand: string;
  model: string;
  year: number | null;
  owner_display_name: string;
  contact_options: string[];
}

export interface VehicleQRResponse {
  qr_code: string;
  scan_path: string;
  scan_url: string;
}

@Injectable({ providedIn: 'root' })
export class ConnectService {
  private http = inject(HttpClient);
  private apiUrl = environment.apiUrl;

  getVehicles(): Observable<ConnectVehicle[]> {
    return this.http.get<ConnectVehicle[]>(`${this.apiUrl}/connect/vehicles/`);
  }

  createVehicle(payload: ConnectVehicleCreate): Observable<ConnectVehicle> {
    return this.http.post<ConnectVehicle>(`${this.apiUrl}/connect/vehicles/`, payload);
  }

  getVehicle(id: number): Observable<ConnectVehicle> {
    return this.http.get<ConnectVehicle>(`${this.apiUrl}/connect/vehicles/${id}/`);
  }

  updateVehicle(id: number, payload: Partial<ConnectVehicleCreate>): Observable<ConnectVehicle> {
    return this.http.patch<ConnectVehicle>(`${this.apiUrl}/connect/vehicles/${id}/`, payload);
  }

  deleteVehicle(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/connect/vehicles/${id}/`);
  }

  getVehicleQr(id: number): Observable<VehicleQRResponse> {
    return this.http.get<VehicleQRResponse>(`${this.apiUrl}/connect/vehicles/${id}/qr/`);
  }

  /** Public – no auth required */
  getVehicleByQr(qrCode: string): Observable<VehicleByQRResponse> {
    return this.http.get<VehicleByQRResponse>(
      `${this.apiUrl}/connect/vehicle/by-qr/${encodeURIComponent(qrCode)}/`
    );
  }

  /** Public – lookup by vehicle registration number; returns same shape as by-qr for scan result page. */
  getVehicleByRegistration(registrationNumber: string): Observable<VehicleByQRResponse> {
    return this.http.get<VehicleByQRResponse>(
      `${this.apiUrl}/connect/vehicle/by-registration/${encodeURIComponent(registrationNumber.trim())}/`
    );
  }

  /** Initiate masked call (Kaleyra click-to-call). Public. */
  initiateCall(qrCode: string, scannerPhone: string): Observable<{ success: boolean; message?: string; data?: unknown }> {
    return this.http.post<{ success: boolean; message?: string; data?: unknown }>(
      `${this.apiUrl}/connect/call/initiate/`,
      { qr_code: qrCode, scanner_phone: scannerPhone }
    );
  }
}
