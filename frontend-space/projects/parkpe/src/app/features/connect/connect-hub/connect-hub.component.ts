import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

/**
 * Connect Hub – main page for logged-in users at /connect.
 * Provides access to Connect product functionalities: vehicles, QR, scan.
 * Product description (marketing) is at /connect/info.
 */
@Component({
  selector: 'app-connect-hub',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './connect-hub.component.html',
  styleUrl: './connect-hub.component.scss',
})
export class ConnectHubComponent {}
