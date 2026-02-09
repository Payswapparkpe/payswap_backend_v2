import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ConnectService, VehicleByQRResponse } from '../services/connect.service';

@Component({
  selector: 'app-connect-scan-result',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-scan-result.component.html',
  styleUrl: './connect-scan-result.component.scss',
})
export class ConnectScanResultComponent implements OnInit {
  private connect = inject(ConnectService);
  private route = inject(ActivatedRoute);

  data = signal<VehicleByQRResponse | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);
  calling = signal(false);
  showPhoneInput = signal(false);
  scannerPhone = signal('');

  ngOnInit() {
    const qrCode = this.route.snapshot.paramMap.get('qrCode');
    if (!qrCode) {
      this.error.set('Invalid QR code');
      this.loading.set(false);
      return;
    }
    this.connect.getVehicleByQr(qrCode).subscribe({
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

  onPhoneInput(e: Event) {
    const v = (e.target as HTMLInputElement)?.value ?? '';
    this.scannerPhone.set(v.replace(/\D/g, '').slice(0, 15));
  }

  contactCall() {
    this.showPhoneInput.set(true);
  }

  cancelCall() {
    this.showPhoneInput.set(false);
    this.scannerPhone.set('');
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
        alert('Call initiated. You will receive a call shortly – answer it to be connected to the vehicle owner (masked).');
      },
      error: (err) => {
        this.calling.set(false);
        alert(err?.error?.detail || 'Failed to initiate call. Please try again.');
      },
    });
  }

  contactChat() {
    alert('Chat – Coming soon. Quick chat will be available in the next update.');
  }
}
