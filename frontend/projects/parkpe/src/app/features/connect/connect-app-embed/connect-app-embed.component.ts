import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { environment } from '../../../../environments/environment';

/**
 * Full Connect app embed – iframe of the Secure Vehicle Communication App.
 * Used from Dashboard so users get the full flow: create QR, vehicles, contact requests, chat, call.
 */
@Component({
  selector: 'app-connect-app-embed',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-app-embed.component.html',
  styleUrl: './connect-app-embed.component.scss',
})
export class ConnectAppEmbedComponent {
  private sanitizer = inject(DomSanitizer);

  readonly connectAppUrl: SafeResourceUrl;
  readonly rawUrl: string;

  constructor() {
    // Only allowlisted URLs (env or this default) – do not use user-controlled URLs
    this.rawUrl =
      (environment as { connectAppUrl?: string }).connectAppUrl ??
      'https://connect.parkpe.in';
    this.connectAppUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.rawUrl);
  }
}
