import { CommonModule } from '@angular/common';
import { Component, ElementRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ParkingService } from '../parking/services/parking.service';

export interface RecentVerification {
  id: string;
  type: 'entry' | 'exit';
  bookingRef: string;
  timeLabel: string;
  summary?: string;
}

@Component({
  selector: 'app-parking-verify',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './parking-verify.component.html',
  styleUrl: './parking-verify.component.scss',
})
export class ParkingVerifyComponent implements OnInit {
  private parking = inject(ParkingService);
  private host = inject(ElementRef<HTMLElement>);

  action = signal<'entry' | 'exit'>('entry');
  bookingRef = '';
  error = signal('');
  successPayload = signal<unknown | null>(null);
  lastSuccessRef = signal('');
  loading = signal(false);
  recent = signal<RecentVerification[]>([]);

  ngOnInit(): void {
    setTimeout(() => this.runPageEntrance(), 0);
  }

  setAction(a: 'entry' | 'exit'): void {
    this.action.set(a);
    this.error.set('');
  }

  submit(): void {
    this.error.set('');
    this.successPayload.set(null);
    const ref = this.bookingRef.trim();
    if (!ref) {
      this.error.set('Enter a booking reference.');
      return;
    }
    this.loading.set(true);
    const req$ =
      this.action() === 'entry' ? this.parking.recordEntry(ref) : this.parking.recordExit(ref);
    req$.subscribe({
      next: (res) => {
        this.loading.set(false);
        this.lastSuccessRef.set(ref);
        this.successPayload.set(res);
        this.bookingRef = '';
        const id = `rv-${Date.now()}`;
        const timeLabel = new Date().toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });
        this.recent.update((list) =>
          [
            {
              id,
              type: this.action(),
              bookingRef: ref,
              timeLabel,
              summary: this.formatSuccessSummary(res),
            },
            ...list,
          ].slice(0, 5),
        );
        setTimeout(() => this.animateRecentItem(id), 0);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err?.error?.detail || err?.message || 'Verification failed');
      },
    });
  }

  successSummaryText(): string {
    return this.formatSuccessSummary(this.successPayload()) ?? '';
  }

  private formatSuccessSummary(res: unknown): string | undefined {
    if (res && typeof res === 'object') {
      const o = res as Record<string, unknown>;
      const plate = o['vehicle_number'] ?? o['vehicleNumber'];
      const slot = o['slot_code'] ?? o['slotCode'];
      const parts: string[] = [];
      if (plate) parts.push(String(plate));
      if (slot) parts.push(`Slot ${slot}`);
      return parts.length ? parts.join(' · ') : undefined;
    }
    return undefined;
  }

  private runPageEntrance(): void {
    const root = this.host.nativeElement;
    const blocks = Array.from(root.querySelectorAll('[data-verify-card]')) as HTMLElement[];
    blocks.forEach((el: HTMLElement, i: number) => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(16px)';
      el.style.transition = 'none';
      requestAnimationFrame(() => {
        setTimeout(() => {
          el.style.transition = 'opacity 350ms ease, transform 350ms ease';
          el.style.opacity = '1';
          el.style.transform = 'translateY(0)';
        }, i * 70);
      });
    });
  }

  private animateRecentItem(id: string): void {
    const el = this.host.nativeElement.querySelector(`[data-recent-id="${id}"]`) as HTMLElement | null;
    if (!el) return;
    el.style.opacity = '0';
    el.style.transform = 'scale(0.94)';
    el.style.transition = 'none';
    requestAnimationFrame(() => {
      el.style.transition = 'opacity 280ms ease, transform 280ms ease';
      el.style.opacity = '1';
      el.style.transform = 'scale(1)';
    });
  }
}
