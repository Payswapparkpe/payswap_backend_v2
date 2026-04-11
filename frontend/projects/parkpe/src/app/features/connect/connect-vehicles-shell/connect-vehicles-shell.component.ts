import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterOutlet } from '@angular/router';
import { ConnectVehiclesListComponent } from '../connect-vehicles-list/connect-vehicles-list.component';

@Component({
  selector: 'app-connect-vehicles-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, ConnectVehiclesListComponent],
  template: `
    <div class="connect-vehicles-shell">
      <div class="service-layout connect-vehicles-shell__grid">
        <aside class="service-col-left">
          <app-connect-vehicles-list [embedded]="true" />
        </aside>
        <main class="service-col-right">
          @if (hasChildRoute()) {
            <router-outlet />
          } @else {
            <div class="service-placeholder connect-vehicles-shell__empty">
              <span class="material-icons connect-vehicles-shell__empty-icon" aria-hidden="true">directions_car</span>
              <p class="service-placeholder-title">Select a vehicle</p>
              <p class="service-placeholder-hint">Pick one from the list to open QR, Connect actions, and RC details.</p>
            </div>
          }
        </main>
      </div>
    </div>
  `,
  styles: [`
    .connect-vehicles-shell {
      padding: clamp(0.75rem, 2vw, 1.25rem);
      max-width: 1480px;
      margin: 0 auto;
    }
    /* Narrower list, wider detail — reduces “three thin columns” feel */
    .connect-vehicles-shell__grid {
      align-items: stretch;
    }
    @media (min-width: 768px) {
      .connect-vehicles-shell__grid {
        grid-template-columns: minmax(0, 288px) minmax(0, 1fr);
        gap: clamp(1.25rem, 3vw, 2.25rem);
      }
      .connect-vehicles-shell__grid .service-col-left {
        max-height: min(88vh, 760px);
        padding: 0 0.35rem 0 0;
        margin: 0;
        background: transparent;
        border: none;
      }
    }
    @media (min-width: 1200px) {
      .connect-vehicles-shell__grid {
        grid-template-columns: minmax(0, 300px) minmax(0, 1fr);
      }
    }
    .connect-vehicles-shell__empty {
      min-height: min(52vh, 22rem);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 2.5rem 1.75rem;
      border-radius: 1rem;
      background: linear-gradient(165deg, #f8fafc 0%, #ffffff 55%);
      border: 1px dashed #cbd5e1;
      box-shadow: none;
    }
    .connect-vehicles-shell__empty-icon {
      font-size: 2.75rem !important;
      color: #94a3b8;
      margin-bottom: 0.75rem;
      opacity: 0.9;
    }
    .connect-vehicles-shell__empty .service-placeholder-title {
      font-size: 1.1rem;
      margin-bottom: 0.35rem;
    }
    .connect-vehicles-shell__empty .service-placeholder-hint {
      max-width: 22rem;
      margin: 0 auto;
    }
  `],
})
export class ConnectVehiclesShellComponent {
  private router = inject(Router);

  hasChildRoute(): boolean {
    const u = this.router.url;
    return u.includes('/connect/vehicles/') && !u.replace(/\/$/, '').endsWith('/connect/vehicles');
  }
}
