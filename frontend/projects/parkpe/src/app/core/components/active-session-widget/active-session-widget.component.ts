import { CommonModule } from '@angular/common';
import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { timer } from 'rxjs';
import { ParkingService } from '../../../features/parking/services/parking.service';
import { ParkingActorService } from '../../services/parking-actor.service';

/**
 * Persistent bottom strip for an in-progress (active) parking session — XState + live timer.
 */
@Component({
  selector: 'app-active-session-widget',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './active-session-widget.component.html',
  styleUrl: './active-session-widget.component.scss',
})
export class ActiveSessionWidgetComponent implements OnInit {
  private parking = inject(ParkingService);
  readonly actor = inject(ParkingActorService);
  private destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.refreshActiveFromHistory();
    timer(0, 60_000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.refreshActiveFromHistory());
  }

  private refreshActiveFromHistory(): void {
    this.parking.getHistory(1, 15).subscribe({
      next: ({ bookings }) => {
        const active = bookings.find((b) => b.status === 'active');
        if (active) {
          this.actor.restoreActiveSession(active);
        } else {
          this.actor.reset();
        }
      },
      error: () => {},
    });
  }

  formatElapsed(totalSec: number): string {
    const s = Math.max(0, Math.floor(totalSec));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(sec)}`;
  }
}
