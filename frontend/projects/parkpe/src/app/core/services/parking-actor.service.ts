import { Injectable, computed, signal } from '@angular/core';
import { createActor, type ActorRefFrom } from 'xstate';
import { filter, interval, Subscription } from 'rxjs';
import { parkingSessionMachine, type ParkingSessionEvent } from '../machines/parking-session.machine';
import type { Booking } from '../models/parking.model';

/**
 * XState-backed active parking session. RxJS `interval` drives TICK while in `entered`.
 * Replaces ad-hoc timers; pair with {@link ActiveSessionWidgetComponent} in the app shell.
 */
@Injectable({ providedIn: 'root' })
export class ParkingActorService {
  private actor: ActorRefFrom<typeof parkingSessionMachine> = createActor(parkingSessionMachine).start();
  private tickSub: Subscription | null = null;

  /** Raw XState snapshot (for debugging / advanced use). */
  readonly snapshot = signal(this.actor.getSnapshot());

  readonly state = computed(() => {
    const v = this.snapshot().value;
    if (typeof v === 'string') return v;
    if (v && typeof v === 'object') return Object.keys(v)[0] ?? 'unknown';
    return 'unknown';
  });
  readonly booking = computed(() => this.snapshot().context.booking);
  readonly elapsedSeconds = computed(() => this.snapshot().context.elapsedSeconds);
  readonly estCost = computed(() => this.snapshot().context.estimatedCostInr);
  readonly errorMessage = computed(() => this.snapshot().context.errorMessage);
  /** Vehicle on-site, timer running (not payment). */
  readonly isActive = computed(() => this.state() === 'entered');
  readonly isPaymentPending = computed(
    () => this.state() === 'paymentPending' || this.state() === 'awaitingUpiPayment'
  );

  constructor() {
    this.actor.subscribe((snap) => this.snapshot.set(snap));
    this.actor.subscribe((snap) => this.syncTickLoop(snap.value));
  }

  send(event: ParkingSessionEvent): void {
    this.actor.send(event);
  }

  /** Restore widget from active booking (e.g. after history fetch). */
  restoreActiveSession(booking: Booking): void {
    const elapsedSeconds = this.elapsedSinceEntry(booking);
    const estimatedCostInr = this.estimateInrForActive(booking, elapsedSeconds);
    this.send({ type: 'RESTORE', booking, elapsedSeconds, estimatedCostInr });
  }

  /** Clear session (after completed / navigate away). */
  reset(): void {
    this.send({ type: 'RESET' });
  }

  private syncTickLoop(value: unknown): void {
    const stateName = typeof value === 'string' ? value : value && typeof value === 'object' ? Object.keys(value as object)[0] : '';
    if (stateName === 'entered') {
      if (this.tickSub) return;
      this.tickSub = interval(1000)
        .pipe(
          filter(() => {
            const s = this.actor.getSnapshot();
            const v = s.value;
            const n = typeof v === 'string' ? v : v && typeof v === 'object' ? Object.keys(v as object)[0] : '';
            return n === 'entered';
          })
        )
        .subscribe(() => {
          const b = this.actor.getSnapshot().context.booking;
          const nextElapsed = this.actor.getSnapshot().context.elapsedSeconds + 1;
          const cost = b ? this.estimateInrForActive(b, nextElapsed) : 0;
          this.send({ type: 'TICK', cost });
        });
    } else {
      this.tickSub?.unsubscribe();
      this.tickSub = null;
    }
  }

  /**
   * Client-side estimate: uses duration × rough hourly from booking amount window.
   * Server remains source of truth at exit; this is for the bottom strip only.
   */
  private elapsedSinceEntry(booking: Booking): number {
    const start = booking.actualEntryTime
      ? new Date(booking.actualEntryTime as string).getTime()
      : new Date(booking.from as string).getTime();
    return Math.max(0, Math.floor((Date.now() - start) / 1000));
  }

  private estimateInrForActive(booking: Booking, elapsedSec: number): number {
    const from = new Date(booking.from as string).getTime();
    const to = new Date(booking.to as string).getTime();
    const plannedMin = Math.max(1, (to - from) / 60000);
    const base = Number(booking.estimatedAmount ?? booking.amount ?? 0);
    const perMin = base / plannedMin;
    const minutes = elapsedSec / 60;
    return Math.round(perMin * minutes * 100) / 100;
  }
}
