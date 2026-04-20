import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { AuthService } from '../../../core/services/auth.service';
import { VoucherService } from '../services/voucher.service';
import { GatewayConfig, PaymentGateway } from 'shared';
import type { VoucherListItem } from '../../../core/models/voucher.model';

@Component({
  selector: 'app-vouchers-page',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="vouchers-page">
      <a routerLink="/dashboard" class="back-link">
        <span class="material-icons">arrow_back</span> Back to Dashboard
      </a>
      <h1 class="page-title">Vouchers</h1>
      <p class="page-subtitle">Buy a new voucher, link one you received, or view your vouchers.</p>

      <div class="two-column">
        <!-- Left: Buy new voucher -->
        <section class="column-left card card-fixed">
          <h2 class="section-title">
            <span class="material-icons">add_circle</span>
            Buy New Voucher
          </h2>
          <p class="section-desc">Add a voucher to pay bills (e.g. BBPS) without Card/UPI.</p>

          <form [formGroup]="form" (ngSubmit)="submit()" class="buy-form">
            <div class="form-group">
              <label>Amount (₹)</label>
              <input type="number" class="form-control" formControlName="amount" placeholder="e.g. 500" min="1" step="1" />
              @if (form.get('amount')?.invalid && form.get('amount')?.touched) {
                <span class="error">Enter a valid amount (min ₹1)</span>
              }
            </div>
            <div class="form-group">
              <label>Payment gateway</label>
              @if (loadingGateways()) {
                <p class="hint">Loading gateways...</p>
              } @else {
                <div class="gateways-list">
                  @for (g of gateways(); track g.name) {
                    <label class="gateway-option">
                      <input type="radio" formControlName="gateway" [value]="g.name" />
                      <span>{{ g.displayName }}</span>
                    </label>
                  }
                </div>
                @if (gateways().length === 0) {
                  <p class="hint">{{ needsLogin() ? 'Please log in to add voucher.' : 'No gateway enabled.' }}</p>
                }
              }
            </div>
            <button type="submit" class="btn btn-primary btn-block" [disabled]="form.invalid || processing() || gateways().length === 0">
              @if (processing()) {
                <span class="spinner-sm"></span> Processing...
              } @else {
                Pay ₹{{ form.get('amount')?.value || 0 }} &amp; Get Voucher
              }
            </button>
          </form>

          @if (!needsLogin()) {
            <div class="link-voucher-block">
              <h3 class="link-title">
                <span class="material-icons">link</span>
                Link existing voucher
              </h3>
              <p class="section-desc">Received a voucher elsewhere? Enter code and PIN to link it to your account.</p>
              <form [formGroup]="claimForm" (ngSubmit)="submitClaim()" class="claim-form">
                <div class="form-group">
                  <label>Voucher code</label>
                  <input type="text" class="form-control" formControlName="voucherCode" placeholder="XXXX-XXXX-XXXX-XXXX" autocomplete="off" />
                </div>
                <div class="form-group">
                  <label>PIN</label>
                  <input type="password" class="form-control" formControlName="pin" placeholder="4-digit PIN" maxlength="12" autocomplete="off" />
                </div>
                @if (claimError()) {
                  <p class="error">{{ claimError() }}</p>
                }
                @if (claimMessage()) {
                  <p class="success-msg">{{ claimMessage() }}</p>
                }
                <button type="submit" class="btn btn-outline btn-block" [disabled]="claimForm.invalid || claimProcessing()">
                  @if (claimProcessing()) {
                    <span class="spinner-sm"></span> Linking…
                  } @else {
                    Link to my account
                  }
                </button>
              </form>
            </div>
          }
        </section>

        <!-- Right: My vouchers (max 3) + View All -->
        <section class="column-right card card-fixed">
          <div class="section-head-row">
            <h2 class="section-title">
              <span class="material-icons">confirmation_number</span>
              My Vouchers
            </h2>
            <a routerLink="/vouchers/list" class="view-all-link">View All</a>
          </div>
          <p class="section-desc">Tap a voucher to view code, PIN and history.</p>

          @if (listLoading()) {
            <div class="loading-state"><div class="spinner"></div></div>
          } @else if (displayVouchers().length === 0) {
            <div class="empty-list">
              <span class="material-icons">card_giftcard</span>
              <p>No vouchers yet. Buy one on the left.</p>
            </div>
          } @else {
            <div class="voucher-cards">
              @for (v of displayVouchers(); track v.id) {
                <a [routerLink]="['/vouchers', v.id]" class="voucher-card">
                  <div class="card-header">
                    <span class="voucher-code">{{ v.voucherCode }}</span>
                    <span class="status-badge" [class]="v.status.toLowerCase()">{{ v.status | titlecase }}</span>
                  </div>
                  <div class="card-amounts">
                    <span class="balance">₹{{ v.currentBalance }}</span>
                    <span class="meta">of ₹{{ v.originalAmount }} · {{ v.issuedAt | date:'shortDate' }}</span>
                  </div>
                  @if (v.linkedUserPhone) {
                    <p class="card-linked">Linked: {{ v.linkedUserPhone }}</p>
                  } @else if (v.parkpeLinked === false) {
                    <p class="card-linked not-linked">Not linked</p>
                  }
                  <span class="material-icons chevron">chevron_right</span>
                </a>
              }
            </div>
            @if (total() > displayVouchers().length) {
              <p class="pagination-hint">Showing {{ displayVouchers().length }} of {{ total() }}</p>
            }
          }
        </section>
      </div>
    </div>
  `,
  styles: [`
    .vouchers-page { padding: 1rem; max-width: 1200px; margin: 0 auto; }
    .back-link {
      display: inline-flex; align-items: center; gap: 0.5rem;
      color: var(--primary-600); text-decoration: none; font-weight: 500; margin-bottom: 1rem;
    }
    .back-link .material-icons { font-size: 20px; }
    .page-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }
    .page-subtitle { color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.9375rem; }

    .two-column {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1.5rem;
    }
    @media (min-width: 900px) {
      .two-column { grid-template-columns: 380px 1fr; }
    }

    .column-left, .column-right {
      padding: 1.5rem;
    }
    .card-fixed {
      min-height: 380px;
      display: flex;
      flex-direction: column;
    }
    .section-head-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
    }
    .section-head-row .section-title { margin-bottom: 0; }
    .view-all-link {
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--primary-600);
      text-decoration: none;
    }
    .view-all-link:hover { text-decoration: underline; }
    .section-title {
      display: flex; align-items: center; gap: 0.5rem;
      font-size: 1.125rem; font-weight: 700; margin-bottom: 0.5rem;
    }
    .section-title .material-icons { font-size: 22px; color: var(--primary-600); }
    .section-desc { color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 1.25rem; }

    .buy-form .form-group { margin-bottom: 1.25rem; }
    .buy-form label { display: block; font-weight: 600; margin-bottom: 0.5rem; font-size: 0.875rem; }
    .form-control { width: 100%; padding: 0.75rem; border: 1px solid var(--border-light); border-radius: var(--radius-md); }
    .error { color: var(--error-600); font-size: 0.8125rem; }
    .gateways-list { display: flex; flex-direction: column; gap: 0.5rem; }
    .gateway-option { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; font-size: 0.9375rem; }
    .gateway-option input { margin: 0; }
    .hint { color: var(--text-muted); font-size: 0.875rem; margin: 0; }
    .btn-block { width: 100%; padding: 0.875rem; margin-top: 0.5rem; display: flex; align-items: center; justify-content: center; gap: 0.5rem; }
    .spinner-sm { width: 18px; height: 18px; border: 2px solid var(--border-light); border-top-color: var(--primary-500); border-radius: 50%; animation: spin 0.8s linear infinite; }

    .loading-state { display: flex; justify-content: center; padding: 2rem; }
    .spinner { width: 36px; height: 36px; border: 3px solid var(--border-light); border-top-color: var(--primary-500); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    .empty-list {
      text-align: center; padding: 2rem 1rem;
    }
    .empty-list .material-icons { font-size: 48px; color: var(--text-muted); margin-bottom: 0.75rem; display: block; }
    .empty-list p { color: var(--text-secondary); font-size: 0.9375rem; margin: 0; }

    .voucher-cards { display: flex; flex-direction: column; gap: 0.75rem; }
    .voucher-card {
      display: block; text-decoration: none; color: inherit; padding: 1rem; border: 1px solid var(--border-light);
      border-radius: var(--radius-md); position: relative; transition: background 0.2s, box-shadow 0.2s;
    }
    .voucher-card:hover { background: var(--surface); box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
    .voucher-card .voucher-code { font-family: monospace; font-size: 0.9375rem; font-weight: 600; }
    .status-badge {
      padding: 0.2rem 0.6rem; border-radius: var(--radius-full); font-size: 0.7rem; font-weight: 600;
    }
    .status-badge.active { background: var(--success); color: white; }
    .status-badge.partially_redeemed { background: var(--warning); color: #1a1a1a; }
    .status-badge.fully_redeemed { background: var(--text-muted); color: white; }
    .card-amounts { display: flex; flex-direction: column; gap: 0.25rem; }
    .card-amounts .balance { font-weight: 700; color: var(--primary-700); font-size: 1.125rem; }
    .card-amounts .meta { font-size: 0.75rem; color: var(--text-muted); }
    .card-linked { font-size: 0.7rem; color: var(--text-secondary); margin: 0.35rem 0 0; padding-right: 1.5rem; }
    .card-linked.not-linked { color: var(--text-muted); }
    .voucher-card .chevron { position: absolute; right: 0.75rem; top: 50%; transform: translateY(-50%); color: var(--text-muted); font-size: 20px; }
    .pagination-hint { font-size: 0.8125rem; color: var(--text-muted); margin-top: 0.75rem; }

    .link-voucher-block {
      margin-top: 1.5rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border-light);
    }
    .link-title {
      display: flex; align-items: center; gap: 0.5rem;
      font-size: 1rem; font-weight: 700; margin-bottom: 0.5rem;
    }
    .link-title .material-icons { font-size: 20px; color: var(--primary-600); }
    .claim-form .form-group { margin-bottom: 1rem; }
    .success-msg { color: var(--success); font-size: 0.875rem; margin: 0 0 0.5rem; }
    .btn-outline { border: 1px solid var(--primary-500); background: transparent; color: var(--primary-700); }
    .btn-outline:disabled { opacity: 0.6; }
  `],
})
export class VouchersPageComponent implements OnInit {
  private paymentService = inject(PaymentGatewayService);
  private authService = inject(AuthService);
  private voucherService = inject(VoucherService);
  private fb = inject(FormBuilder);
  private router = inject(Router);

  form: FormGroup = this.fb.group({
    amount: [500, [Validators.required, Validators.min(1)]],
    gateway: [null as PaymentGateway | null, Validators.required],
  });
  claimForm: FormGroup = this.fb.group({
    voucherCode: ['', Validators.required],
    pin: ['', Validators.required],
  });
  gateways = signal<GatewayConfig[]>([]);
  loadingGateways = signal(true);
  processing = signal(false);
  claimProcessing = signal(false);
  claimError = signal<string | null>(null);
  claimMessage = signal<string | null>(null);
  needsLogin = signal(false);

  vouchers = signal<VoucherListItem[]>([]);
  total = signal(0);
  listLoading = signal(true);

  ngOnInit() {
    if (!this.authService.getToken()) {
      this.needsLogin.set(true);
      this.loadingGateways.set(false);
      this.listLoading.set(false);
      return;
    }
    this.paymentService.getAvailableGateways().subscribe({
      next: (list) => {
        this.gateways.set(list ?? []);
        if (list?.length) this.form.patchValue({ gateway: list[0].name });
        this.loadingGateways.set(false);
      },
      error: () => this.loadingGateways.set(false),
    });
    this.loadVouchers();
  }

  /** Max 3 vouchers shown on main page; full list on View All page */
  readonly MAX_PREVIEW = 3;
  displayVouchers = computed(() => this.vouchers().slice(0, this.MAX_PREVIEW));

  loadVouchers() {
    this.listLoading.set(true);
    this.voucherService.getVouchers({ limit: 50 }).subscribe({
      next: (res) => {
        this.vouchers.set(res.vouchers ?? []);
        this.total.set(res.total ?? 0);
        this.listLoading.set(false);
      },
      error: () => this.listLoading.set(false),
    });
  }

  submit() {
    if (this.form.invalid || this.processing()) return;
    const amount = Number(this.form.get('amount')?.value);
    const gateway = this.form.get('gateway')?.value as PaymentGateway;
    this.processing.set(true);
    const request = {
      amount,
      currency: 'INR',
      orderId: '',
      orderDescription: 'Voucher purchase',
      transactionType: 'other' as const,
      customer: { name: 'Customer', email: '', phone: '' },
    };
    this.paymentService.initiatePayment(gateway, request).subscribe({
      next: () => {
        this.processing.set(false);
        this.router.navigate(['/payment/status'], {
          queryParams: { status: 'success' },
        });
      },
      error: () => this.processing.set(false),
    });
  }

  submitClaim() {
    if (!this.authService.getToken()) return;
    if (this.claimForm.invalid || this.claimProcessing()) return;
    this.claimProcessing.set(true);
    this.claimError.set(null);
    this.claimMessage.set(null);
    const voucherCode = (this.claimForm.get('voucherCode')?.value ?? '').toString().trim();
    const pin = (this.claimForm.get('pin')?.value ?? '').toString().trim();
    this.voucherService.claimVoucher(voucherCode, pin).subscribe({
      next: (res) => {
        this.claimProcessing.set(false);
        this.claimMessage.set(res.message);
        this.claimForm.reset({ voucherCode: '', pin: '' });
        this.loadVouchers();
      },
      error: (err: { error?: { detail?: string | string[] } }) => {
        this.claimProcessing.set(false);
        const d = err?.error?.detail;
        const msg = Array.isArray(d) ? d[0] : d;
        this.claimError.set(
          typeof msg === 'string' && msg.trim()
            ? msg
            : 'Could not link voucher. Check the code and PIN.'
        );
      },
    });
  }
}
