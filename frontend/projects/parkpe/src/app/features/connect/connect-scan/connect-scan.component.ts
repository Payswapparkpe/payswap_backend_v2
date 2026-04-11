import { Component, inject, signal, OnDestroy, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { ConnectService } from '../services/connect.service';

/**
 * Connect scan – in-app. Options: scan QR with camera, enter QR code, or search by vehicle number.
 * On success navigates to /connect/scan/:qrCode (scan result: vehicle + Call/Chat).
 */
@Component({
  selector: 'app-connect-scan',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-scan.component.html',
  styleUrl: './connect-scan.component.scss',
})
export class ConnectScanComponent implements AfterViewInit, OnDestroy {
  private router = inject(Router);
  private connect = inject(ConnectService);

  code = signal('');
  vehicleNumber = signal('');
  searchError = signal<string | null>(null);
  searchLoading = signal(false);
  cameraActive = signal(false);
  cameraError = signal<string | null>(null);
  scannerLibReady = signal(false);

  private scanner: import('html5-qrcode').Html5Qrcode | null = null;
  private Html5QrcodeClass: typeof import('html5-qrcode').Html5Qrcode | null = null;

  ngAfterViewInit() {
    this.loadScannerLib();
  }

  ngOnDestroy() {
    this.stopCamera();
  }

  private async loadScannerLib() {
    try {
      const mod = await import('html5-qrcode');
      this.Html5QrcodeClass = mod.Html5Qrcode;
      this.scannerLibReady.set(true);
    } catch {
      this.Html5QrcodeClass = null;
    }
  }

  /** Extract QR code from scanned text (URL or raw code). */
  private parseScannedCode(decodedText: string): string {
    const t = decodedText.trim();
    const scanPath = '/connect/scan/';
    const idx = t.indexOf(scanPath);
    if (idx !== -1) {
      const after = t.slice(idx + scanPath.length);
      const end = after.indexOf('?');
      return end === -1 ? after.split('/')[0] : after.slice(0, end);
    }
    if (t.includes('/scan/')) {
      const parts = t.split('/scan/');
      const after = parts[parts.length - 1];
      return after.split('/')[0].split('?')[0];
    }
    return t;
  }

  startCamera() {
    if (!this.Html5QrcodeClass) {
      this.cameraError.set('Camera scanner not available. Use “Enter QR code” or “Search by vehicle number” below.');
      return;
    }
    this.stopCamera();
    this.cameraError.set(null);
    const el = document.getElementById('qr-reader');
    if (!el) {
      this.cameraError.set('Scanner element not found.');
      return;
    }
    // Brief delay so previous scanner can release the camera/dom
    setTimeout(() => {
      if (!this.Html5QrcodeClass) return;
      this.scanner = new this.Html5QrcodeClass('qr-reader');
      const config = { fps: 10, qrbox: { width: 220, height: 220 } };
      this.scanner!
        .start(
          { facingMode: 'environment' },
          config,
          (decodedText) => {
            this.stopCamera();
            const code = this.parseScannedCode(decodedText);
            if (code) this.router.navigate(['/connect/scan', code]);
          },
          () => {} // qrCodeErrorCallback – ignore scan errors (no QR in frame)
        )
        .then(() => this.cameraActive.set(true))
        .catch((err: Error) => {
          this.cameraError.set(err?.message || 'Could not start camera.');
          this.scanner = null;
        });
    }, 150);
  }

  stopCamera(): void {
    if (this.scanner) {
      const s = this.scanner;
      this.scanner = null;
      this.cameraActive.set(false);
      s.stop().catch(() => {});
    } else {
      this.cameraActive.set(false);
    }
  }

  onCodeInput(e: Event) {
    this.code.set((e.target as HTMLInputElement)?.value ?? '');
  }

  onVehicleNumberInput(e: Event) {
    this.vehicleNumber.set((e.target as HTMLInputElement)?.value ?? '');
    this.searchError.set(null);
  }

  goToScanResult() {
    const c = this.code().trim();
    if (!c) return;
    this.router.navigate(['/connect/scan', c]);
  }

  searchByVehicleNumber() {
    const reg = this.vehicleNumber().trim();
    if (!reg) return;
    this.searchError.set(null);
    this.searchLoading.set(true);
    this.connect.getVehicleByRegistration(reg).subscribe({
      next: (res) => {
        this.searchLoading.set(false);
        this.router.navigate(['/connect/scan', res.qr_code]);
      },
      error: (err) => {
        this.searchLoading.set(false);
        this.searchError.set(err?.error?.detail || 'Vehicle not found. Try another number or use QR.');
      },
    });
  }
}
