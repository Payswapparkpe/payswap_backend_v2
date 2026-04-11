import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { environment } from '../../../../environments/environment';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { NotificationService } from '../../../core/services/notification.service';
import { AuthService } from '../../../core/services/auth.service';
import { HttpErrorResponse } from '@angular/common/http';
import { finalize } from 'rxjs/operators';
import type { BBPSOperator } from '../../../core/models/bbps.model';

@Component({
  selector: 'app-fastag-confirm',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="feature-container">
      <h1 class="feature-title">Confirm Recharge</h1>

      @if (!recharge) {
        <div class="empty-state card">
          <p>No recharge details. <a routerLink="/fastag/recharge">Start recharge</a></p>
        </div>
      } @else {
        <div class="layout-grid">
          <div class="operators-panel card">
            <h3>Operators</h3>
            <input
              class="form-control search-input"
              type="text"
              placeholder="Search operator"
              [value]="searchTerm"
              (input)="searchTerm = $any($event.target).value || ''"
              [disabled]="loadingOperators || loading"
            />
            <div class="operator-list">
              @if (loadingOperators) {
                <div class="operator-empty">Loading operators...</div>
              } @else if (!operators.length) {
                <div class="operator-empty">No FASTag operators available</div>
              } @else {
                @for (op of filteredOperators; track op.id) {
                  <button
                    type="button"
                    class="operator-item"
                    [class.active]="selectedOperatorId === op.id"
                    (click)="onOperatorChange(op.id)"
                    [disabled]="loading"
                  >
                    <div class="operator-row">
                      <img class="operator-icon" [src]="getOperatorIconUrl(op)" [alt]="op.name" loading="lazy" />
                      <div class="operator-meta">
                        <span class="op-name">{{ op.name }}</span>
                        <span class="op-code">{{ op.code }}</span>
                      </div>
                    </div>
                  </button>
                }
              }
            </div>
          </div>
          <div class="confirm-card card">
            <h2>Recharge Summary</h2>
            <div class="detail-row">
              <span>Operator:</span>
              <span class="summary-operator">
                @if (selectedOperator) {
                  <img class="summary-operator-icon" [src]="getOperatorIconUrl(selectedOperator)" [alt]="selectedOperator.name" loading="lazy" />
                }
                <span>{{ selectedOperator?.name || 'Select FASTag operator' }}</span>
              </span>
            </div>
            <div class="detail-row"><span>Vehicle Number:</span><span>{{ recharge.vehicleNumber }}</span></div>
            <div class="detail-row highlight">
              <span>Recharge Amount:</span><span class="amount">₹{{ recharge.amount }}</span>
            </div>

            <button class="btn btn-primary btn-block" (click)="confirmRecharge()" [disabled]="loading">
              @if (loading) {
                <span class="spinner"></span> Processing...
              } @else {
                Proceed to Payment
              }
            </button>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 0; max-width: 100%; }
    .feature-title { font-size: 1.25rem; font-weight: 700; margin: 0 0 1.25rem; }
    .empty-state { padding: 2rem; text-align: center; }
    .layout-grid {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 1rem;
      align-items: start;
    }
    .operators-panel { padding: 1rem; }
    .operators-panel h3 { margin: 0 0 0.75rem; font-size: 1rem; }
    .search-input { margin-bottom: 0.75rem; }
    .operator-list { max-height: 430px; overflow: auto; display: grid; gap: 0.5rem; }
    .operator-item {
      text-align: left;
      width: 100%;
      border: 1px solid var(--border-light);
      border-radius: var(--radius-md);
      background: #fff;
      padding: 0.65rem 0.75rem;
      cursor: pointer;
      display: grid;
      gap: 0.1rem;
    }
    .operator-row { display: flex; align-items: center; gap: 0.65rem; }
    .operator-meta { min-width: 0; display: grid; gap: 0.08rem; }
    .operator-icon {
      width: 2.8rem;
      height: 1.45rem;
      object-fit: contain;
      border: 1px solid var(--border-light);
      border-radius: 0.3rem;
      background: #fff;
      padding: 0.08rem;
      flex-shrink: 0;
    }
    .operator-item.active { border-color: var(--primary-500); background: var(--primary-50); }
    .op-name { font-weight: 600; font-size: 0.88rem; color: var(--text-primary); }
    .op-code { font-size: 0.75rem; color: var(--text-secondary); }
    .operator-empty { font-size: 0.86rem; color: var(--text-secondary); padding: 0.5rem 0.25rem; }
    .confirm-card { padding: 2rem; }
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light);

      &.highlight {
        background: var(--primary-50);
        padding: 1rem;
        border-radius: var(--radius-md);
        margin: 1rem 0;
        border-bottom: none;
      }
    }
    .amount { font-size: 1.5rem; font-weight: 700; color: var(--primary-700); }
    .summary-operator {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      justify-content: flex-end;
    }
    .summary-operator-icon {
      width: 2rem;
      height: 1rem;
      object-fit: contain;
      border: 1px solid var(--border-light);
      border-radius: 0.25rem;
      background: #fff;
      padding: 0.06rem;
      flex-shrink: 0;
    }
    .btn-block { width: 100%; padding: 1rem; margin-top: 1rem; }
    @media (max-width: 980px) {
      .layout-grid { grid-template-columns: 1fr; }
      .operator-list { max-height: 240px; }
    }
  `],
})
export class FastagConfirmComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);
  private notification = inject(NotificationService);
  private auth = inject(AuthService);
  private readonly mobikwikOperatorIconBase = environment.mobikwikIconBase;

  recharge: { vehicleNumber: string; amount: number; operatorId?: string; operatorCode?: string; operatorName?: string } | null = null;
  customer = { name: 'User', email: '', phone: '+919876543210' };
  loading = false;
  loadingOperators = false;
  operators: BBPSOperator[] = [];
  searchTerm = '';
  selectedOperatorId = '';
  get filteredOperators(): BBPSOperator[] {
    const q = (this.searchTerm || '').trim().toLowerCase();
    if (!q) return this.operators;
    return this.operators.filter((o) =>
      `${o.name} ${o.code}`.toLowerCase().includes(q)
    );
  }
  get selectedOperator(): BBPSOperator | null {
    return this.operators.find((o) => o.id === this.selectedOperatorId) || null;
  }

  ngOnInit() {
    const state = this.router.getCurrentNavigation()?.extras?.state ?? history.state;
    this.recharge = state['recharge'] ?? null;
    if (!this.recharge) {
      this.recharge = null;
      return;
    }
    this.loadFastagOperators();
    this.auth.getProfile().subscribe({
      next: (user) => {
        this.customer = {
          name: user.name ?? 'User',
          email: user.email ?? '',
          phone: user.phone ?? this.customer.phone,
        };
      },
    });
  }

  onOperatorChange(value: string) {
    this.selectedOperatorId = String(value || '').trim();
  }

  private loadFastagOperators() {
    this.loadingOperators = true;
    this.api.getOperators('fastag').subscribe({
      next: (ops) => {
        this.operators = Array.isArray(ops) ? ops : [];
        this.loadingOperators = false;
        if (this.operators.length === 1) {
          this.selectedOperatorId = this.operators[0].id;
        } else if (this.operators.length === 0) {
          this.notification.showError('FASTag operators not configured. Please import Mobikwik operators sheet.');
        }
      },
      error: () => {
        this.loadingOperators = false;
        this.notification.showError('Unable to load FASTag operators');
      },
    });
  }

  confirmRecharge() {
    if (!this.recharge) return;
    if (!this.selectedOperatorId) {
      this.notification.showError('Please select FASTag operator');
      return;
    }
    const selectedOp = this.operators.find((o) => o.id === this.selectedOperatorId);
    this.loading = true;
    this.api.createRechargeOrder({
      operatorId: this.selectedOperatorId,
      operatorCode: selectedOp?.code || this.selectedOperatorId,
      operatorName: selectedOp?.name || '',
      vehicleNumber: this.recharge.vehicleNumber,
      amount: Number(this.recharge.amount),
      customerName: this.customer.name,
      customerEmail: this.customer.email || 'user@example.com',
      customerPhone: this.customer.phone,
    }).pipe(
      finalize(() => {
        this.loading = false;
      })
    ).subscribe({
      next: () => {
        this.notification.showSuccess('FASTag recharged successfully!');
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.notification.showError(this.getRechargeErrorMessage(err));
      },
    });
  }

  private getRechargeErrorMessage(error?: unknown): string {
    if (error instanceof HttpErrorResponse) {
      const detail =
        (error.error && (error.error.detail || error.error.message)) ||
        error.message;
      if (detail) return String(detail);
    }
    if (error instanceof Error && error.message) return error.message;
    return 'Recharge failed';
  }

  getOperatorIconUrl(operator?: BBPSOperator | null): string {
    const explicitLogo = String(operator?.logo ?? '').trim();
    if (explicitLogo && !explicitLogo.includes('bharat-connect-logo')) {
      return explicitLogo;
    }
    const raw = String(operator?.mobikwikOpId ?? '').trim();
    if (/^\d+\.0$/.test(raw)) {
      return `${this.mobikwikOperatorIconBase}/op${raw.slice(0, -2)}.png`;
    }
    if (/^\d+$/.test(raw)) {
      return `${this.mobikwikOperatorIconBase}/op${raw}.png`;
    }
    if (/^op\d+$/i.test(raw)) {
      return `${this.mobikwikOperatorIconBase}/${raw.toLowerCase()}.png`;
    }
    return 'assets/bbps/bharat-connect-logo.png';
  }
}
