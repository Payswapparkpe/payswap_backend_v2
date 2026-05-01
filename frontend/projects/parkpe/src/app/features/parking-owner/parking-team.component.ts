import { CommonModule } from '@angular/common';
import { Component, ElementRef, inject, OnInit, signal, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ParkingService } from '../parking/services/parking.service';

@Component({
  selector: 'app-parking-team',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './parking-team.component.html',
  styleUrl: './parking-team.component.scss',
})
export class ParkingTeamComponent implements OnInit {
  private parking = inject(ParkingService);
  private host = inject(ElementRef<HTMLElement>);

  @ViewChild('invitePanel') invitePanel?: ElementRef<HTMLDivElement>;

  locationId = signal('');
  locations = signal<{ id: number; name: string }[]>([]);
  operators = signal<Record<string, unknown>[]>([]);
  email = '';
  username = '';
  role: 'owner' | 'manager' | 'attendant' = 'attendant';
  error = signal('');
  inviteOpen = signal(false);
  busyId = signal<number | null>(null);

  ngOnInit(): void {
    this.parking.getOwnerLocations().subscribe({
      next: (res: { locations?: { id: number; name: string }[] }) => {
        const locs = res?.locations ?? [];
        this.locations.set(locs.map((l) => ({ id: l.id, name: l.name ?? `Loc ${l.id}` })));
        const first = locs[0];
        if (first) {
          this.locationId.set(String(first.id));
          this.loadTeam();
        }
      },
    });
  }

  toggleInvite(): void {
    const open = !this.inviteOpen();
    this.inviteOpen.set(open);
    setTimeout(() => {
      const panel = this.invitePanel?.nativeElement;
      if (!panel) return;
      if (open) {
        panel.style.maxHeight = panel.scrollHeight + 'px';
        panel.style.opacity = '1';
      } else {
        panel.style.maxHeight = '0';
        panel.style.opacity = '0';
      }
    }, 0);
  }

  loadTeam(): void {
    const lid = this.locationId();
    if (!lid) return;
    this.error.set('');
    this.parking.getOwnerTeam(lid).subscribe({
      next: (res: { operators?: Record<string, unknown>[] }) => {
        this.operators.set(res?.operators ?? []);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load team');
      },
    });
  }

  onLocationChange(id: string): void {
    this.locationId.set(id);
    this.loadTeam();
  }

  add(): void {
    const lid = this.locationId();
    if (!lid) return;
    this.error.set('');
    this.parking
      .createOwnerTeamUser(lid, {
        email: this.email || undefined,
        username: this.username || undefined,
        role: this.role,
      })
      .subscribe({
        next: () => {
          this.email = '';
          this.username = '';
          this.role = 'attendant';
          this.inviteOpen.set(false);
          const panel = this.invitePanel?.nativeElement;
          if (panel) { panel.style.maxHeight = '0'; panel.style.opacity = '0'; }
          this.loadTeam();
        },
        error: (err) => {
          this.error.set(err?.error?.detail || 'Failed to add operator');
        },
      });
  }

  deactivate(op: Record<string, unknown>): void {
    const lid = this.locationId();
    const id = Number(op['id']);
    if (!lid || !id) return;
    this.busyId.set(id);
    this.parking.deactivateOwnerTeamUser(lid, id).subscribe({
      next: () => {
        this.busyId.set(null);
        this.operators.update((list) =>
          list.map((o) =>
            Number(o['id']) === id ? { ...o, isActive: false } : o,
          ),
        );
      },
      error: (err) => {
        this.busyId.set(null);
        this.error.set(err?.error?.detail || 'Failed to deactivate');
      },
    });
  }

  initials(name: unknown, username: unknown, email: unknown): string {
    const s = String(name || username || email || '?').trim();
    const parts = s.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return s.slice(0, 2).toUpperCase();
  }

  roleClass(r: unknown): string {
    const role = String(r || '').toLowerCase();
    if (role === 'owner') return 'bg-violet-100 text-violet-800 ring-violet-200';
    if (role === 'manager') return 'bg-indigo-100 text-indigo-800 ring-indigo-200';
    return 'bg-emerald-100 text-emerald-800 ring-emerald-200';
  }

  avatarGradient(r: unknown): string {
    const role = String(r || '').toLowerCase();
    if (role === 'owner') return 'bg-gradient-to-br from-violet-500 to-indigo-600';
    if (role === 'manager') return 'bg-gradient-to-br from-sky-500 to-indigo-600';
    return 'bg-gradient-to-br from-emerald-500 to-teal-600';
  }
}
