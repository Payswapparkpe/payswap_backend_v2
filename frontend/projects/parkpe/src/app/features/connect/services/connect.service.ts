import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';

/** Cashfree Vehicle RC API response (key fields for display) */
export interface VehicleRCData {
  status?: string;
  reg_no?: string;
  vehicle_manufacturer_name?: string;
  model?: string;
  vehicle_colour?: string;
  type?: string;
  rc_status?: string;
  reg_authority?: string;
  reg_date?: string;
  rc_expiry_date?: string;
  vehicle_insurance_company_name?: string;
  vehicle_insurance_upto?: string;
  chassis?: string;
  engine?: string;
  // Added fields for strict typing
  owner?: string;
  vehicle_category?: string;
  pucc_upto?: string;
  vehicle_cubic_capacity?: string;
  is_commercial?: boolean;
  [key: string]: unknown;
}

export type VehicleTypeId = 'two_wheeler' | 'four_wheeler' | 'commercial';

export interface ConnectVehicle {
  id: number;
  vehicle_type: string;
  registration_number: string;
  brand: string;
  model: string;
  year: number | null;
  photo: string | null;
  is_primary: boolean;
  qr_code: string | null;
  created_at: string;
  updated_at: string;
  vehicle_rc?: VehicleRCData | null;
  /** Alias for vehicle_rc to support legacy template access */
  rc_data?: VehicleRCData | null;
  /** True when RC exists but profile name does not match RC owner and user has not unlocked. */
  rc_locked?: boolean;
  /**
   * True when this vehicle has no RC row yet but is not the user's first Connect vehicle:
   * user must pay ₹50 (voucher) before fetch-rc will run (matches backend fetch-rc gate).
   */
  rc_payment_required_before_fetch?: boolean;
  /** When owner paid Rs 50 from voucher to view full RC (ISO date string). */
  rc_view_paid_at?: string | null;
  /** BBPS FASTag biller id (Mobikwik); user-selected issuer. */
  fastag_biller_id?: string | null;
  /** Cached FASTag balance from BBPS View Bill (last refresh). */
  fastag_balance?: number | null;
  /** ISO time when fastag_balance was last fetched. */
  fastag_balance_fetched_at?: string | null;
}

export interface ConnectVehicleCreate {
  vehicle_type?: string;
  registration_number: string;
  brand?: string;
  model?: string;
  year?: number | null;
  photo?: string | null;
  is_primary?: boolean;
  /** Required when creating: user must accept ownership declaration. */
  accept_ownership_declaration?: boolean;
  /** FASTag issuer (BBPS biller id); four_wheeler / commercial. */
  fastag_biller_id?: string;
}

/** Meta returned with vehicle list: individual max 4, corporate unlimited. */
export interface ConnectVehiclesMeta {
  user_type: 'individual' | 'corporate' | 'business';
  vehicle_count: number;
  max_vehicles: number | null;
  can_add_more: boolean;
}

export interface ConnectVehiclesListResponse {
  results: ConnectVehicle[];
  meta: ConnectVehiclesMeta;
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

  /** List vehicles; returns results + meta (user_type, max_vehicles, can_add_more). */
  getVehicles(): Observable<ConnectVehiclesListResponse> {
    return this.http.get<ConnectVehiclesListResponse | ConnectVehicle[]>(`${this.apiUrl}/connect/vehicles/`).pipe(
      map((res) => {
        const isLegacy = Array.isArray(res);
        const results = isLegacy ? (res as ConnectVehicle[]) : (res as ConnectVehiclesListResponse).results;
        const meta = isLegacy
          ? { user_type: 'individual' as const, vehicle_count: results.length, max_vehicles: 4, can_add_more: true }
          : (res as ConnectVehiclesListResponse).meta;
        return {
          results: (results || []).map((v) => ({ ...v, rc_data: v.vehicle_rc })),
          meta,
        };
      })
    );
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

  /** Refresh FASTag balance via BBPS View Bill (requires fastag_biller_id on vehicle). */
  refreshVehicleFastagBalance(vehicleId: number): Observable<ConnectVehicle> {
    return this.http.post<ConnectVehicle>(`${this.apiUrl}/connect/vehicles/${vehicleId}/fastag-balance/`, {});
  }

  /** Request OTP for vehicle deletion (sends OTP to user's registered mobile). */
  requestDeleteOtp(vehicleId: number): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${this.apiUrl}/connect/vehicles/${vehicleId}/delete-request/`,
      {}
    );
  }

  /** Confirm vehicle deletion with OTP. Returns 204 on success. */
  confirmDeleteVehicle(vehicleId: number, otp: string): Observable<void> {
    return this.http.post<void>(
      `${this.apiUrl}/connect/vehicles/${vehicleId}/delete/`,
      { otp: otp.trim() }
    );
  }

  /** Fetch RC data from API and return updated vehicle with vehicle_rc. */
  fetchVehicleRc(vehicleId: number): Observable<ConnectVehicle> {
    return this.http.post<ConnectVehicle>(
      `${this.apiUrl}/connect/vehicles/${vehicleId}/fetch-rc/`,
      {}
    );
  }

  /** Verify ownership with owner name, chassis, engine to unlock RC view. Returns 200 with { unlocked: true } on success. */
  unlockVehicleRc(
    vehicleId: number,
    payload: { owner_name: string; chassis_number: string; engine_number: string }
  ): Observable<{ unlocked: boolean }> {
    return this.http.post<{ unlocked: boolean }>(
      `${this.apiUrl}/connect/vehicles/${vehicleId}/unlock-rc/`,
      payload
    );
  }

  /** Pay Rs 50 from selected voucher (voucher_id + pin) to unlock full RC view. Returns { paid: true, vehicle } or { already_paid: true, vehicle }. */
  payRcView(
    vehicleId: number,
    body: { voucher_id: number; pin: string }
  ): Observable<{ paid?: boolean; already_paid?: boolean; vehicle: ConnectVehicle }> {
    return this.http.post<{ paid?: boolean; already_paid?: boolean; vehicle: ConnectVehicle }>(
      `${this.apiUrl}/connect/vehicles/${vehicleId}/pay-rc-view/`,
      body
    );
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
  /**
   * Initiate call. When the user is logged in (or just verified via scanner OTP), the backend uses
   * their profile phone; scannerPhone is ignored in that case. When not logged in, pass a call_token
   * from getCallToken() instead.
   */
  initiateCall(qrCode: string, scannerPhoneOrCallToken: string, useCallToken = false): Observable<{ success: boolean; message?: string; data?: unknown }> {
    const body = useCallToken
      ? { qr_code: qrCode, call_token: scannerPhoneOrCallToken }
      : { qr_code: qrCode, scanner_phone: scannerPhoneOrCallToken };
    return this.http.post<{ success: boolean; message?: string; data?: unknown }>(
      `${this.apiUrl}/connect/call/initiate/`,
      body
    );
  }

  /** Get a short-lived call token after OTP verify (for unauthenticated call flow). */
  getCallToken(qrCode: string, scannerPhone: string, otp: string): Observable<{ call_token: string; expires_in: number }> {
    return this.http.post<{ call_token: string; expires_in: number }>(
      `${this.apiUrl}/connect/call/token/`,
      { qr_code: qrCode, scanner_phone: scannerPhone, otp: otp.trim() }
    );
  }

  /** Scanner (unregistered) flow: send OTP to phone. Rate-limited. */
  scannerSendOtp(phone: string, qrCode: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiUrl}/connect/scanner/send-otp/`, {
      phone: phone.trim(),
      qr_code: qrCode || '',
    });
  }

  /** Scanner (unregistered) flow: verify OTP; returns JWT + user (existing or new minimal customer). */
  scannerVerifyOtp(phone: string, otp: string, qrCode: string): Observable<ConnectScannerVerifyResponse> {
    return this.http.post<ConnectScannerVerifyResponse>(`${this.apiUrl}/connect/scanner/verify-otp/`, {
      phone: phone.trim(),
      otp: otp.trim(),
      qr_code: qrCode || '',
    });
  }

  /** Chat: list predefined messages (public). */
  getPredefinedMessages(): Observable<ConnectPredefinedMessageDto[]> {
    return this.http.get<ConnectPredefinedMessageDto[]>(`${this.apiUrl}/connect/chat/predefined-messages/`);
  }

  /** Chat: get or create thread by qr_code (auth). */
  getOrCreateThread(qrCode: string): Observable<ConnectThreadDto> {
    return this.http.post<ConnectThreadDto>(`${this.apiUrl}/connect/chat/threads/`, { qr_code: qrCode });
  }

  /** Chat: list my threads (auth). */
  getThreads(): Observable<ConnectThreadDto[]> {
    return this.http.get<ConnectThreadDto[]>(`${this.apiUrl}/connect/chat/threads/`);
  }

  /** Chat: get single thread by id (auth). */
  getThread(threadId: number): Observable<ConnectThreadDto> {
    return this.http.get<ConnectThreadDto>(`${this.apiUrl}/connect/chat/threads/${threadId}/`);
  }

  /** Chat: list messages in thread (auth). Optional ?after=messageId for polling. */
  getThreadMessages(threadId: number, after?: number): Observable<ConnectMessageDto[]> {
    const options = after != null ? { params: { after: String(after) } } : {};
    return this.http.get<ConnectMessageDto[]>(
      `${this.apiUrl}/connect/chat/threads/${threadId}/messages/`,
      options
    );
  }

  /** Report a user (from chat). Auth required. */
  reportUser(threadId: number, reportedUserId: number, reason: string): Observable<{ id: number; status: string; message: string }> {
    return this.http.post<{ id: number; status: string; message: string }>(
      `${this.apiUrl}/connect/report/`,
      { thread_id: threadId, reported_user_id: reportedUserId, reason: reason.trim() }
    );
  }

  /** Chat: send text or predefined message (auth). */
  sendMessage(
    threadId: number,
    payload:
      | { message_type: 'text'; body: string; client_id?: string; metadata?: Record<string, unknown> }
      | { message_type: 'predefined'; predefined_code: string; client_id?: string; metadata?: Record<string, unknown> }
      | { message_type: 'attachment' | 'voice'; body: string; client_id?: string; metadata?: Record<string, unknown> }
  ): Observable<ConnectMessageDto> {
    return this.http.post<ConnectMessageDto>(
      `${this.apiUrl}/connect/chat/threads/${threadId}/messages/`,
      payload
    );
  }

  markThreadRead(threadId: number): Observable<{ ok: boolean; last_read_message_id: number }> {
    return this.http.post<{ ok: boolean; last_read_message_id: number }>(
      `${this.apiUrl}/connect/chat/threads/${threadId}/mark-read/`,
      {}
    );
  }

  sendThreadPresence(threadId: number, typing = false): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.apiUrl}/connect/chat/threads/${threadId}/presence/`, { typing });
  }

  getThreadPresence(threadId: number): Observable<{ other_online: boolean; other_typing: boolean }> {
    return this.http.get<{ other_online: boolean; other_typing: boolean }>(
      `${this.apiUrl}/connect/chat/threads/${threadId}/presence/`
    );
  }

  updateThreadSettings(
    threadId: number,
    payload: Partial<{ pinned: boolean; muted: boolean; archived: boolean }>
  ): Observable<{ pinned: boolean; muted: boolean; archived: boolean }> {
    return this.http.patch<{ pinned: boolean; muted: boolean; archived: boolean }>(
      `${this.apiUrl}/connect/chat/threads/${threadId}/settings/`,
      payload
    );
  }

  blockThreadParticipant(threadId: number, action: 'block' | 'unblock', reason = ''): Observable<{ blocked: boolean; message: string }> {
    return this.http.post<{ blocked: boolean; message: string }>(
      `${this.apiUrl}/connect/chat/threads/${threadId}/block/`,
      { action, reason }
    );
  }
}

export interface ConnectPredefinedMessageDto {
  code: string;
  label_en: string;
  label_hi: string;
  body_en: string;
  body_hi: string;
}

export interface ConnectThreadDto {
  id: number;
  vehicle_id: number;
  registration_number_masked: string;
  owner_display_name: string;
  /** Other participant's first name for chat header/inbox — never a phone number. */
  peer_display_name?: string;
  scanner_user_id?: number;
  is_owner?: boolean;
  other_participant_id?: number;
  pinned?: boolean;
  muted?: boolean;
  archived?: boolean;
  unread_count?: number;
  last_read_message_id?: number;
  last_message_id?: number | null;
  last_message_preview?: string;
  last_message_created_at?: string | null;
  other_online?: boolean;
  other_typing?: boolean;
}

export interface ConnectMessageDto {
  id: number;
  sender_id: number;
  message_type: string;
  body: string;
  metadata?: Record<string, unknown>;
  client_id?: string;
  delivery_status?: 'sending' | 'sent' | 'delivered' | 'seen' | 'failed';
  delivered_at?: string | null;
  seen_at?: string | null;
  local_failed?: boolean;
  predefined_code?: string | null;
  created_at: string;
}

/** Response from scanner verify-otp (same shape as login for session). */
export interface ConnectScannerVerifyResponse {
  token: string;
  refreshToken: string;
  user: { id: string; name: string; email: string; phone: string; role?: string;[key: string]: unknown };
  is_new_user: boolean;
}
