import { Component, inject, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  ConnectService,
  VehicleByQRResponse,
  ConnectPredefinedMessageDto,
} from '../services/connect.service';
import { ConnectChatService } from '../services/connect-chat.service';
import { AuthService } from '@core/services/auth.service';
import { ToastService } from '../../../ui/toast/toast.service';

@Component({
  selector: 'app-connect-scan-result',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-scan-result.component.html',
  styleUrl: './connect-scan-result.component.scss',
})
export class ConnectScanResultComponent implements OnInit, OnDestroy {
  private connect = inject(ConnectService);
  public chatService = inject(ConnectChatService); // Public for HTML access
  private route = inject(ActivatedRoute);
  private auth = inject(AuthService);
  private toast = inject(ToastService);

  qrCode = signal<string | null>(null);
  data = signal<VehicleByQRResponse | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);
  /** True after scanner verified via OTP (or already logged in). Then we show Call/Chat. */
  scannerVerified = signal(false);
  showScannerPhoneStep = signal(false);
  showScannerOtpStep = signal(false);
  scannerPhoneValue = signal('');
  scannerOtpValue = signal('');
  sendOtpLoading = signal(false);
  verifyOtpLoading = signal(false);
  sendOtpError = signal<string | null>(null);
  verifyOtpError = signal<string | null>(null);

  calling = signal(false);
  showPhoneInput = signal(false);
  scannerPhone = signal('');
  callError = signal<string | null>(null);
  callErrorIs502 = signal(false);

  showChatPanel = signal(false);
  chatPredefined = signal<ConnectPredefinedMessageDto[]>([]);
  chatMessageInput = signal('');
  chatOpening = signal(false);
  chatOtherParticipantId = signal<number | null>(null); // Kept for reporting

  // Local state for non-chat logic
  showReportModal = signal(false);
  reportReason = signal('');
  reportSubmitting = signal(false);
  reportError = signal<string | null>(null);

  /** Show vehicle card + Call/Chat only when we have data and (user is logged in or scanner just verified). */
  showContactOptions = computed(() => {
    const d = this.data();
    const verified = this.scannerVerified();
    const isAuth = this.auth.isAuthenticatedSignal();
    return !!d && (isAuth || verified);
  });

  currentUserId = computed(() => {
    const u = this.auth.userSignal();
    const id = u?.id;
    return id != null ? Number(id) : null;
  });

  /** Show "Enter your mobile to continue" when we have vehicle data but user not verified. */
  showScannerGate = computed(() => {
    const d = this.data();
    const loading = this.loading();
    const verified = this.scannerVerified();
    const isAuth = this.auth.isAuthenticatedSignal();
    return !loading && !!d && !isAuth && !verified && !this.showScannerOtpStep();
  });

  ngOnInit() {
    const code = this.route.snapshot.paramMap.get('qrCode');
    if (!code) {
      this.error.set('Invalid QR code');
      this.loading.set(false);
      return;
    }
    this.qrCode.set(code);
    this.scannerVerified.set(this.auth.isAuthenticatedSignal());
    this.connect.getVehicleByQr(code).subscribe({
      next: (res) => {
        this.data.set(res);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Invalid or expired QR code');
        this.loading.set(false);
      },
    });
  }

  onScannerPhoneInput(e: Event) {
    const v = (e.target as HTMLInputElement)?.value ?? '';
    this.scannerPhoneValue.set(v.replace(/\D/g, '').slice(0, 15));
    this.sendOtpError.set(null);
  }

  onScannerOtpInput(e: Event) {
    const v = (e.target as HTMLInputElement)?.value ?? '';
    this.scannerOtpValue.set(v.replace(/\D/g, '').slice(0, 8));
    this.verifyOtpError.set(null);
  }

  sendScannerOtp() {
    const phone = this.scannerPhoneValue().trim();
    const code = this.qrCode();
    if (!phone || !code) return;
    this.sendOtpError.set(null);
    this.sendOtpLoading.set(true);
    this.connect.scannerSendOtp(phone, code).subscribe({
      next: () => {
        this.sendOtpLoading.set(false);
        this.showScannerPhoneStep.set(false);
        this.showScannerOtpStep.set(true);
      },
      error: (err) => {
        this.sendOtpLoading.set(false);
        this.sendOtpError.set(err?.error?.detail || 'Failed to send OTP. Please try again.');
      },
    });
  }

  verifyScannerOtp() {
    const phone = this.scannerPhoneValue().trim();
    const otp = this.scannerOtpValue().trim();
    const code = this.qrCode();
    if (!phone || !otp || !code) return;
    this.verifyOtpError.set(null);
    this.verifyOtpLoading.set(true);
    this.connect.scannerVerifyOtp(phone, otp, code).subscribe({
      next: (res) => {
        this.verifyOtpLoading.set(false);
        this.auth.setSessionFromConnectScanner({
          ...res,
          user: { ...res.user, role: (res.user.role === 'admin' ? 'admin' : 'user') as 'user' | 'admin' },
        });
        this.scannerVerified.set(true);
        this.showScannerOtpStep.set(false);
        this.scannerOtpValue.set('');
      },
      error: (err) => {
        this.verifyOtpLoading.set(false);
        this.verifyOtpError.set(err?.error?.detail || 'Invalid or expired OTP. Please try again.');
      },
    });
  }

  openScannerPhoneStep() {
    this.showScannerPhoneStep.set(true);
    this.sendOtpError.set(null);
  }

  contactChat() {
    const code = this.qrCode();
    if (!code) return;

    // Check if duplicate call (panel already open)
    if (this.showChatPanel()) return;

    this.chatOpening.set(true);
    this.connect.getOrCreateThread(code).subscribe({
      next: (thread) => {
        this.chatOpening.set(false);
        this.showChatPanel.set(true);
        this.chatOtherParticipantId.set(thread.other_participant_id ?? null);

        // Use Chat Service
        this.chatService.loadThread(thread.id, thread.other_participant_id ?? null);

        // Load predefined
        this.connect.getPredefinedMessages().subscribe({
          next: (list) => this.chatPredefined.set(list),
          error: () => { },
        });
      },
      error: (err) => {
        this.chatOpening.set(false);
        const raw = err?.error?.detail;
        const msg =
          typeof raw === 'string'
            ? raw
            : Array.isArray(raw)
              ? raw.map((x: unknown) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' ')
              : 'Failed to open chat.';
        this.chatService.setError(msg);
        this.toast.error(msg);
        this.showChatPanel.set(true); // open panel so error is visible (UX-002: no blocking alert)
      },
    });
  }

  closeChat() {
    this.showChatPanel.set(false);
    this.chatService.clearThread();
    this.chatMessageInput.set('');
  }

  onChatMessageInput(e: Event) {
    this.chatMessageInput.set((e.target as HTMLInputElement)?.value ?? '');
  }

  sendChatMessage() {
    const body = this.chatMessageInput().trim();
    if (!body) return;
    this.chatService.sendMessage(body);
    this.chatMessageInput.set('');
  }

  sendPredefinedMessage(code: string) {
    this.chatService.sendMessage('', true, code);
  }

  prefLabel(pref: ConnectPredefinedMessageDto): string {
    const lang = (navigator.language || '').toLowerCase();
    if (lang.startsWith('hi') && pref.label_hi?.trim()) {
      return pref.label_hi;
    }
    return pref.label_en;
  }

  openReportModal() {
    this.reportReason.set('');
    this.reportError.set(null);
    this.showReportModal.set(true);
  }

  closeReportModal() {
    this.showReportModal.set(false);
    this.reportError.set(null);
  }

  onReportReasonInput(e: Event) {
    this.reportReason.set((e.target as HTMLTextAreaElement)?.value ?? '');
  }

  submitReport() {
    const tid = this.chatService.threadId();
    const otherId = this.chatOtherParticipantId();
    const reason = this.reportReason().trim();
    if (!tid || !otherId || !reason) return;
    this.reportSubmitting.set(true);
    this.reportError.set(null);
    this.connect.reportUser(tid, otherId, reason).subscribe({
      next: () => {
        this.reportSubmitting.set(false);
        this.closeReportModal();
      },
      error: (err) => {
        this.reportSubmitting.set(false);
        this.reportError.set(err?.error?.detail || 'Failed to submit report.');
      },
    });
  }

  ngOnDestroy() {
    this.chatService.clearThread();
  }

  onPhoneInput(e: Event) {
    const v = (e.target as HTMLInputElement)?.value ?? '';
    this.scannerPhone.set(v.replace(/\D/g, '').slice(0, 15));
  }

  contactCall() {
    this.callError.set(null);
    this.callErrorIs502.set(false);
    const user = this.auth.userSignal();
    if (user?.phone) {
      const p = user.phone.replace(/\D/g, '').slice(-10);
      this.scannerPhone.set(p || '');
    } else {
      this.scannerPhone.set('');
    }
    this.showPhoneInput.set(true);
  }

  cancelCall() {
    this.showPhoneInput.set(false);
    this.scannerPhone.set('');
    this.callError.set(null);
    this.callErrorIs502.set(false);
  }

  confirmCall() {
    const d = this.data();
    const phone = this.scannerPhone().trim();
    if (!d || !phone) return;
    this.calling.set(true);
    const num = phone.length === 10 && !phone.startsWith('91') ? `91${phone}` : phone;
    this.connect.initiateCall(d.qr_code, num).subscribe({
      next: () => {
        this.calling.set(false);
        this.showPhoneInput.set(false);
        this.scannerPhone.set('');
        this.toast.success('Call initiated. You will receive a masked bridge call shortly.');
      },
      error: (err) => {
        this.calling.set(false);
        const detail = err?.error?.detail || 'Failed to initiate call. Please try again.';
        const is502 = err?.status === 502;
        this.callError.set(detail);
        this.callErrorIs502.set(is502);
        this.toast.error(detail);
      },
    });
  }
}
