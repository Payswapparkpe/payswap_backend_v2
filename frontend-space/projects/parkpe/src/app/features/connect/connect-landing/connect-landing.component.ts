import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { environment } from '../../../../environments/environment';

/**
 * Connect service landing – ParkPe Connect (Secure Vehicle Communication).
 * Explains the service and links to the full Connect app (connect.parkpe.in).
 */
@Component({
  selector: 'app-connect-landing',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-landing.component.html',
  styleUrl: './connect-landing.component.scss',
})
export class ConnectLandingComponent {
  getConnectQR() {
    this.openConnectAppAsOwner();
  }

  scanAQr() {
    this.openConnectAppScan();
  }

  /** Full Connect app URL (QR-based vehicle communication) */
  readonly connectAppUrl = (environment as { connectAppUrl?: string }).connectAppUrl ?? 'https://connect.parkpe.in';

  readonly features = [
    { icon: 'qr_code_2', title: 'Unique QR sticker', description: 'Each vehicle gets a scannable QR code' },
    { icon: 'shield', title: 'No phone number sharing', description: 'Privacy for both parties' },
    { icon: 'lock', title: 'OTP verification', description: 'Secure authentication for every interaction' },
    { icon: 'chat', title: 'Chat or call', description: 'Connect without exposing personal numbers' },
    { icon: 'block', title: 'Anti-spam', description: 'Built-in safeguards against misuse' },
  ];

  readonly steps = [
    { num: '01', title: 'Vehicle owner registers', desc: 'Quick registration with mobile verification' },
    { num: '02', title: 'Get a unique QR sticker', desc: 'Stick it on your vehicle' },
    { num: '03', title: 'Someone scans the QR', desc: 'Any smartphone camera works' },
    { num: '04', title: 'OTP verification', desc: 'Both parties verify securely' },
    { num: '05', title: 'Secure communication', desc: 'Chat or call without revealing numbers' },
  ];

  openConnectApp() {
    window.open(this.connectAppUrl, '_blank', 'noopener,noreferrer');
  }

  openConnectAppAsOwner() {
    window.open(this.connectAppUrl, '_blank', 'noopener,noreferrer');
  }

  openConnectAppScan() {
    window.open(`${this.connectAppUrl}?scan=1`, '_blank', 'noopener,noreferrer');
  }
}
