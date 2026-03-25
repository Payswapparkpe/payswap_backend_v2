import {
  Component,
  inject,
  OnInit,
  signal,
  computed,
  ViewChild,
  ElementRef,
  afterNextRender,
} from '@angular/core';
import { CommonModule, NgOptimizedImage } from '@angular/common';
import { environment } from '../../../../environments/environment';
import {
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  Validators,
  AbstractControl,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';
import { PaymentGatewayService } from '../../../core/services/payment-gateway.service';
import { VoucherService } from '../../voucher/services/voucher.service';
import type { VoucherListItem } from '../../../core/models/voucher.model';
import {
  BBPSOperator,
  BillFetchResponse,
  BBPSParameter,
  BBPSPaymentRequest,
} from '../../../core/models/bbps.model';
import { BBPSStorageService, SavedBill, FavoriteBiller } from '../services/bbps-storage.service';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';
import gsap from 'gsap';
import { from } from 'rxjs';
import { concatMap, filter, map, take } from 'rxjs/operators';

type Step = 'category' | 'operator' | 'form' | 'bill' | 'pay';

/** Category groups for UI: Recharges, Utilities, Finance & Taxes (match Bharat Billpay screen). */
const CATEGORY_GROUPS: { groupKey: string; groupLabel: string; categories: string[] }[] = [
  {
    groupKey: 'recharges',
    groupLabel: 'Recharges',
    categories: ['prepaid', 'dth', 'subscription', 'cable', 'postpaid'],
  },
  {
    groupKey: 'utilities',
    groupLabel: 'Utilities',
    categories: [
      'electricity',
      'lpg_booking',
      'water',
      'gas',
      'mobile_postpaid',
      'broadband',
      'landline',
      'broadband_postpaid',
      'education',
      'prepaid_meter',
    ],
  },
  {
    groupKey: 'finance_taxes',
    groupLabel: 'Finance & Taxes',
    categories: [
      'loan_repayment',
      'insurance',
      'municipal_taxes',
      'emi_payment',
      'credit_card',
      'donation',
    ],
  },
];

@Component({
  selector: 'app-bbps-internal',
  standalone: true,
  imports: [CommonModule, NgOptimizedImage, ReactiveFormsModule, StepIndicatorComponent, RouterLink],
  templateUrl: './bbps-internal.component.html',
  styleUrl: './bbps-internal.component.scss',
})
export class BBPSInternalComponent implements OnInit {
  private readonly mobikwikOperatorIconBase = environment.mobikwikIconBase;
  private api = inject(API_BACKEND_TOKEN);
  private authService = inject(AuthService);
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private notification = inject(NotificationService);
  private bbpsStorage = inject(BBPSStorageService);
  private paymentService = inject(PaymentGatewayService);
  private voucherService = inject(VoucherService);

  @ViewChild('contentBlock') contentBlock!: ElementRef<HTMLElement>;
  @ViewChild('bbpsMogo') bbpsMogoRef!: ElementRef<HTMLAudioElement>;

  /** Step labels for the indicator; getter so binding is always defined (avoids NG0100). */
  get stepLabels(): string[] {
    return ['Category', 'Operator', 'Consumer Details', 'Pay'];
  }

  step = signal<Step>('category');
  categories = signal<string[]>([]);
  operators = signal<BBPSOperator[]>([]);
  selectedCategory = signal<string | null>(null);
  selectedOperator = signal<BBPSOperator | null>(null);
  bill = signal<BillFetchResponse | null>(null);
  loadingCategories = signal(true);
  loadingOperators = signal(false);
  loadingBill = signal(false);
  paying = signal(false);

  billForm: FormGroup = this.fb.group({});
  billerSearchQuery = signal('');
  billNickname = signal('');
  paymentMethod = signal<'voucher' | 'pg'>('voucher');
  /** Editable when acceptPartPay; otherwise equals bill.amount */
  payableAmount = signal<number>(0);

  /** Voucher pay modal: select voucher + PIN + confirm */
  voucherModalOpen = signal(false);
  voucherModalVouchers = signal<VoucherListItem[]>([]);
  voucherModalLoading = signal(false);
  voucherPayVoucherId = signal<number>(0);
  voucherPayPin = signal('');
  voucherPayConfirmStep = signal(false);
  voucherPayError = signal<string | null>(null);
  voucherPaying = signal(false);
  /** True when voucher modal is for paying cart (multiple bills) */
  voucherPayForCart = signal(false);

  /** Cart: multiple bills to pay together with voucher (total ≤ 10,000; voucher only). */
  cart = signal<BillFetchResponse[]>([]);
  readonly CART_MAX_TOTAL = 10_000;
  cartTotal = computed(() => this.cart().reduce((s, b) => s + b.amount, 0));
  cartCount = computed(() => this.cart().length);
  /** Effective amount to pay for current bill. When acceptPartPay: user-editable (payableAmount); else full bill amount. */
  currentPayableAmount = computed(() => {
    const b = this.bill();
    if (!b) return 0;
    if (!b.acceptPartPay) return b.amount;
    const max = b.amount;
    const min = b.minBillAmount ?? 0;
    let pay = this.payableAmount();
    if (pay <= 0) pay = max;
    return Math.max(min, Math.min(max, pay));
  });
  canAddCurrentBillToCart = computed(() => {
    const b = this.bill();
    if (!b) return false;
    const amt = this.currentPayableAmount();
    return this.cartTotal() + amt <= this.CART_MAX_TOTAL;
  });

  readonly categoryGroups = CATEGORY_GROUPS;

  currentStepIndex = computed(() => {
    const s = this.step();
    switch (s) {
      case 'category':
        return 1;
      case 'operator':
        return 2;
      case 'form':
      case 'bill':
        return 3;
      case 'pay':
        return 4;
      default:
        return 1;
    }
  });

  private categoryIcons: Record<string, string> = {
    electricity: 'bolt',
    water: 'water_drop',
    gas: 'local_fire_department',
    dth: 'tv',
    broadband: 'wifi',
    mobile_postpaid: 'smartphone',
    landline: 'phone',
    insurance: 'shield',
    loan_repayment: 'account_balance',
    municipal_taxes: 'account_balance_wallet',
    education: 'school',
    subscription: 'subscriptions',
    credit_card: 'credit_card',
    emi_payment: 'payment',
    prepaid: 'phone_android',
    postpaid: 'smartphone',
    broadband_postpaid: 'wifi',
    cable: 'tv',
    donation: 'volunteer_activism',
    lpg_booking: 'local_fire_department',
    prepaid_meter: 'speed',
    fastag: 'directions_car',
  };

  /** Display labels for category tiles (match Bharat Billpay UI) */
  private categoryLabels: Record<string, string> = {
    prepaid: 'Mobile Recharge',
    postpaid: 'Postpaid Mobile',
    lpg_booking: 'Book a Cylinder',
    gas: 'Piped Gas',
    municipal_taxes: 'Municipal Tax',
    emi_payment: 'EMI Payment',
    credit_card: 'Credit Card',
    broadband_postpaid: 'Broadband Postpaid',
    prepaid_meter: 'Prepaid Meter',
    subscription: 'FASTag',
    cable: 'Cable TV',
  };

  /** Categories that exist in loaded list, grouped (RECHARGES, UTILITIES, FINANCE & TAXES only). Deduplicated. */
  categoriesByGroup = computed(() => {
    const allCategories = new Set(this.categories());
    return CATEGORY_GROUPS.map((g) => ({
      ...g,
      categories: g.categories.filter((c) => allCategories.has(c)),
    })).filter((g) => g.categories.length > 0);
  });

  /** Filter operators by search */
  filteredOperators = computed(() => {
    const q = this.billerSearchQuery().toLowerCase().trim();
    const list = this.operators();
    if (!q) return list;
    return list.filter(
      (op) =>
        op.name.toLowerCase().includes(q) ||
        (op.code && op.code.toLowerCase().includes(q))
    );
  });

  favoriteOperatorIds = this.bbpsStorage.favoriteOperatorIds;
  favoriteBillersList = this.bbpsStorage.favoriteBillersList;
  savedBillsList = this.bbpsStorage.savedBillsList;

  /** Favorited operators from current list (for star icon state) */
  favoriteOperatorsFromList = computed(() => {
    const ids = new Set(this.bbpsStorage.favoriteOperatorIds());
    return this.operators().filter((op) => ids.has(op.id));
  });

  isFavorite(opId: string): boolean {
    return this.bbpsStorage.isFavorite(opId);
  }

  toggleFavorite(opId: string, event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    const op = this.operators().find((o) => o.id === opId);
    const name = op?.name;
    const category = this.selectedCategory();
    this.bbpsStorage.toggleFavorite(opId, name ?? undefined, category ?? undefined, op?.mobikwikOpId);
  }

  removeFavoriteBiller(fav: FavoriteBiller): void {
    this.bbpsStorage.toggleFavorite(fav.operatorId);
    this.notification.showInfo(`"${fav.operatorName}" removed from favorites.`);
  }

  removeSavedBillFromList(saved: SavedBill): void {
    this.bbpsStorage.removeSavedBill(saved.id);
    this.notification.showInfo(`"${saved.nickname || saved.operatorName}" removed from saved bills.`);
  }

  selectFavoriteBiller(fav: FavoriteBiller): void {
    const openWithCategory = (category: string, ops: BBPSOperator[]) => {
      this.selectedCategory.set(category);
      this.operators.set(ops);
      this.step.set('operator');
      this.loadingOperators.set(false);
      const op = ops.find((o) => o.id === fav.operatorId);
      if (op) {
        this.selectedOperator.set(op);
        this.bill.set(null);
        this.billForm = this.fb.group({});
        this.buildForm(op);
        this.step.set('form');
      } else {
        this.notification.showError('Biller no longer available');
      }
    };

    this.step.set('operator');
    this.loadingOperators.set(true);

    if (fav.category) {
      this.api.getOperators(fav.category).subscribe({
        next: (ops) => {
          const list = ops ?? [];
          openWithCategory(fav.category!, list);
        },
        error: () => {
          this.loadingOperators.set(false);
          this.notification.showError('Failed to load billers');
        },
      });
      return;
    }

    // Category missing (e.g. old favorite): find which category has this operator
    this.api.getCategories().subscribe({
      next: (list) => {
        const categories = Array.isArray(list) ? list : (list as { categories?: string[] }).categories ?? [];
        if (categories.length === 0) {
          this.loadingOperators.set(false);
          this.notification.showError('Could not open favorite. No categories available.');
          return;
        }
        from(categories)
          .pipe(
            concatMap((cat) =>
              this.api.getOperators(cat).pipe(map((ops) => ({ cat, ops: ops ?? [] })))
            ),
            filter(({ ops }) => ops.some((o) => o.id === fav.operatorId)),
            take(1)
          )
          .subscribe({
            next: ({ cat, ops }) => openWithCategory(cat, ops),
            error: () => {
              this.loadingOperators.set(false);
              this.notification.showError('Failed to load billers');
            },
            complete: () => {
              if (this.loadingOperators()) {
                this.loadingOperators.set(false);
                this.notification.showError('Biller no longer available');
              }
            },
          });
      },
      error: () => {
        this.loadingOperators.set(false);
        this.notification.showError('Failed to load categories');
      },
    });
  }

  selectOperator(operator: BBPSOperator) {
    this.selectedOperator.set(operator);
    this.bill.set(null);
    this.billNickname.set('');
    this.buildForm(operator);
    this.step.set('form');
  }

  selectSavedBill(saved: SavedBill): void {
    this.notification.showInfo(`Opening ${saved.nickname || saved.operatorName}. Enter consumer ID to fetch latest bill.`);
    this.selectedCategory.set(saved.category);
    this.step.set('operator');
    this.loadingOperators.set(true);
    this.api.getOperators(saved.category).subscribe({
      next: (ops) => {
        this.operators.set(ops ?? []);
        this.loadingOperators.set(false);
        const op = (ops ?? []).find((o) => o.id === saved.operatorId);
        if (op) {
          this.selectedOperator.set(op);
          this.bill.set(null);
          this.billForm = this.fb.group({});
          this.buildForm(op);
          const firstParam = op.parameters?.[0]?.name;
          if (firstParam) {
            this.billForm.patchValue({ [firstParam]: saved.consumerId });
          }
          this.step.set('form');
        }
      },
      error: () => {
        this.loadingOperators.set(false);
        this.notification.showError('Failed to load operator');
      },
    });
  }

  constructor() {
    afterNextRender(() => {
      const el = this.contentBlock?.nativeElement;
      if (el) {
        gsap.fromTo(el, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.3, ease: 'power2.out' });
      }
    });
  }

  ngOnInit() {
    // Only call API when authenticated so we never send request without token (avoids 401)
    if (this.authService.getToken()) {
      this.loadCategories();
      this.bbpsStorage.refreshFavorites();
      this.bbpsStorage.refreshSavedBills();
    } else {
      this.loadingCategories.set(false);
    }
  }

  /** Play Bharat Connect MOGO sonic identity (BBPS guidelines) – only on successful payment. */
  playBharatConnectMogo() {
    setTimeout(() => {
      const audio = this.bbpsMogoRef?.nativeElement;
      if (audio) {
        audio.volume = 0.5;
        audio.play().catch(() => { /* autoplay policy may block */ });
      }
    }, 300);
  }

  getCategoryIcon(cat: string): string {
    return this.categoryIcons[cat] ?? 'receipt';
  }

  getCategoryLabel(cat: string): string {
    return this.categoryLabels[cat] ?? cat.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  }

  getOperatorIconUrl(
    operator?: { logo?: string; id?: string; code?: string; mobikwikOpId?: string } | null,
    fallbackOperatorId?: string | null
  ): string {
    const explicitLogo = (operator?.logo ?? '').toString().trim();
    // RealApiService normalizes icons; trust payload first.
    if (explicitLogo && !explicitLogo.includes('bharat-connect-logo')) {
      return explicitLogo;
    }

    const candidates = [operator?.mobikwikOpId, fallbackOperatorId];
    for (const raw of candidates) {
      const value = (raw ?? '').toString().trim();
      if (!value) continue;
      if (value.endsWith('.0') && /^\d+\.0$/.test(value)) {
        const num = value.slice(0, -2);
        return `${this.mobikwikOperatorIconBase}/op${num}.png`;
      }
      const lower = value.toLowerCase();
      if (/^op\d+$/.test(lower)) {
        return `${this.mobikwikOperatorIconBase}/${lower}.png`;
      }
      if (/^\d+$/.test(value)) {
        return `${this.mobikwikOperatorIconBase}/op${value}.png`;
      }
    }
    return 'assets/bbps/bharat-connect-logo.png';
  }

  loadCategories() {
    this.loadingCategories.set(true);
    this.api.getCategories().subscribe({
      next: (list) => {
        this.categories.set(Array.isArray(list) ? list : (list as { categories?: string[] }).categories ?? []);
        this.loadingCategories.set(false);
      },
      error: () => {
        this.loadingCategories.set(false);
        this.notification.showError('Failed to load bill categories');
      },
    });
  }

  selectCategory(category: string) {
    this.selectedCategory.set(category);
    this.selectedOperator.set(null);
    this.bill.set(null);
    this.billForm = this.fb.group({});
    // Defer step and API call to next tick to avoid ExpressionChangedAfterItHasBeenCheckedError (NG0100)
    setTimeout(() => {
      this.step.set('operator');
      this.loadingOperators.set(true);
      this.api.getOperators(category).subscribe({
        next: (ops) => {
          this.operators.set(ops ?? []);
          this.loadingOperators.set(false);
        },
        error: () => {
          this.loadingOperators.set(false);
          this.notification.showError('Failed to load operators');
        },
      });
    }, 0);
  }

  private buildForm(operator: BBPSOperator) {
    const group: Record<string, AbstractControl> = {};
    const params = (operator.parameters ?? []).filter((p) => !/^Additional \d+$/i.test(p.label?.trim() ?? ''));
    for (const p of params) {
      const validators = p.required ? [Validators.required] : [];
      if (p.maxLength) validators.push(Validators.maxLength(p.maxLength));
      if (p.minLength) validators.push(Validators.minLength(p.minLength));
      group[p.name] = this.fb.control('', validators);
    }
    this.billForm = this.fb.group(group);
  }

  /** Form params to show in UI; excludes "Additional 1", "Additional 2", … "Additional 5" placeholder fields. */
  getFormParams(): BBPSParameter[] {
    const op = this.selectedOperator();
    const params = op?.parameters ?? [];
    return params.filter((p) => !/^Additional \d+$/i.test(p.label?.trim() ?? ''));
  }

  goBackToCategory() {
    this.step.set('category');
    this.selectedCategory.set(null);
    this.selectedOperator.set(null);
    this.operators.set([]);
    this.bill.set(null);
    this.billForm = this.fb.group({});
    this.billerSearchQuery.set('');
    this.billNickname.set('');
  }

  goBackToOperator() {
    this.step.set('operator');
    this.selectedOperator.set(null);
    this.bill.set(null);
    this.billForm = this.fb.group({});
    this.billNickname.set('');
  }

  goBackToForm() {
    this.step.set('form');
    this.bill.set(null);
    this.payableAmount.set(0);
  }

  /** Normalize raw Mobikwik response to ParkPe BillFetchResponse format. */
  private normalizeBillResponse(
    data: Record<string, unknown>,
    op: BBPSOperator,
    parameters: Record<string, string | number>
  ): Record<string, unknown> {
    if (data['billId'] && data['operatorId'] && (data['amount'] !== undefined || (data as { amount?: number })['amount'] === 0)) {
      return data;
    }
    const arr = data['data'] as unknown[] | undefined;
    if (!Array.isArray(arr) || arr.length === 0) return data;
    const item = arr[0] as Record<string, unknown>;
    if (!item || typeof item !== 'object') return data;

    const nested = (item['Data'] ?? item['data']) as Record<string, unknown> | undefined;
    const dueDate = (item['dueDate'] ?? item['due_date'] ?? nested?.['dueDate'] ?? nested?.['due_date']) as string | undefined;
    const amountVal =
      (item['billAmount'] ?? item['billnetamount'] ?? item['amount'] ?? item['minBillAmount'] ?? 0) as string | number;
    const amount = typeof amountVal === 'string' ? parseFloat(amountVal) || 0 : Number(amountVal) || 0;
    const consumerName = (item['userName'] ?? item['user_name'] ?? item['consumerName'] ?? item['customerName'] ?? '') as string;
    const consumerId = String(
      parameters['consumerId'] ?? parameters['connectionId'] ?? parameters['customer_id'] ?? item['cellNumber'] ?? item['cell_number'] ?? ''
    );

    const acceptPartPay = (item['acceptPartPay'] ?? item['accept_part_pay']) === true || (item['acceptPartPay'] ?? item['accept_part_pay']) === 'true';
    const minBillAmount = item['minBillAmount'] ?? item['min_bill_amount'];
    const minBillNum = typeof minBillAmount === 'number' ? minBillAmount : typeof minBillAmount === 'string' ? parseFloat(minBillAmount) || undefined : undefined;

    const billDetails: { label: string; value: string | number }[] = [];
    const skip = new Set([
      'billAmount', 'billnetamount', 'amount', 'minBillAmount', 'Data', 'data', 'dueDate', 'due_date',
      'userName', 'user_name', 'consumerName', 'customerName', 'cellNumber', 'cell_number',
      'acceptPartPay', 'accept_part_pay', 'min_bill_amount',
    ]);
    for (const [k, v] of Object.entries(item)) {
      if (skip.has(k) || v == null || v === '') continue;
      if (typeof v === 'object') continue;
      billDetails.push({ label: k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()), value: String(v) });
    }

    return {
      ...data,
      billId: data['billId'] ?? `bill_${Date.now()}`.slice(0, 20),
      operatorId: op.id,
      operatorCode: op.code,
      operatorName: op.name,
      mobikwikOpId: op.mobikwikOpId,
      consumerId,
      consumerName: consumerName || undefined,
      dueDate: dueDate ?? '',
      amount,
      billDetails,
      acceptPartPay,
      minBillAmount: minBillNum,
    };
  }

  fetchBill() {
    if (this.billForm.invalid) {
      this.billForm.markAllAsTouched();
      return;
    }
    const op = this.selectedOperator();
    if (!op) return;

    this.loadingBill.set(true);
    const parameters: Record<string, string | number> = {};
    for (const key of Object.keys(this.billForm.value)) {
      const v = this.billForm.value[key];
      if (v !== '' && v != null) parameters[key] = typeof v === 'number' ? v : String(v).trim();
    }

    this.api
      .fetchBill({
        operatorId: op.id,
        operatorCode: op.code,
        parameters,
      })
      .subscribe({
        next: (data) => {
          this.loadingBill.set(false);
          const d = data as { success?: boolean; detail?: string; billId?: string; data?: unknown[] };
          if (d?.success === false || (d?.detail && !d?.billId)) {
            this.notification.showError(typeof d?.detail === 'string' ? d.detail : 'Failed to fetch bill');
            return;
          }
          // Normalize raw Mobikwik response: { success, data: [{ billAmount, Data: { dueDate }, userName, ... }] }
          const normalized = this.normalizeBillResponse(data as unknown as Record<string, unknown>, op, parameters);
          this.bill.set(normalized as unknown as BillFetchResponse);
          const amt = Number((normalized as { amount?: number }).amount ?? 0);
          this.payableAmount.set(amt);
          this.billNickname.set('');
          this.step.set('bill');
        },
        error: (err) => {
          this.loadingBill.set(false);
          const msg = err?.error?.detail || err?.message || 'Failed to fetch bill';
          this.notification.showError(typeof msg === 'string' ? msg : 'Failed to fetch bill');
        },
      });
  }

  setPayableAmountFromInput(val: string | number): void {
    const n = typeof val === 'string' ? parseFloat(val) || 0 : val;
    this.payableAmount.set(n);
  }

  addToCart(): void {
    const b = this.bill();
    if (!b) return;
    const amt = this.currentPayableAmount();
    const total = this.cartTotal() + amt;
    if (total > this.CART_MAX_TOTAL) {
      this.notification.showError(`Cart total cannot exceed ₹${this.CART_MAX_TOTAL.toLocaleString()}. Current total would be ₹${total.toFixed(2)}.`);
      return;
    }
    const item = { ...b, amount: amt };
    this.cart.update((c) => [...c, item]);
    this.notification.showSuccess('Added to cart. You can add more bills or pay cart with voucher.');
  }

  removeFromCart(index: number): void {
    this.cart.update((c) => c.filter((_, i) => i !== index));
  }

  openVoucherPayModal(): void {
    const b = this.bill();
    if (!b) return;
    this.voucherPayForCart.set(false);
    this.voucherModalOpen.set(true);
    this.voucherPayError.set(null);
    this.voucherPayVoucherId.set(0);
    this.voucherPayPin.set('');
    this.voucherPayConfirmStep.set(false);
    this.voucherModalLoading.set(true);
    this.voucherModalVouchers.set([]);
    const amt = this.currentPayableAmount();
    this.voucherService.getVouchers({ limit: 100 }).subscribe({
      next: (res) => {
        const eligible = (res.vouchers ?? []).filter((v) => v.currentBalance >= amt);
        this.voucherModalVouchers.set(eligible);
        this.voucherModalLoading.set(false);
        if (eligible.length === 1) this.voucherPayVoucherId.set(eligible[0].id);
      },
      error: () => {
        this.voucherModalVouchers.set([]);
        this.voucherModalLoading.set(false);
      },
    });
  }

  openVoucherPayModalForCart(): void {
    if (this.cartCount() === 0) return;
    const total = this.cartTotal();
    this.voucherPayForCart.set(true);
    this.voucherModalOpen.set(true);
    this.voucherPayError.set(null);
    this.voucherPayVoucherId.set(0);
    this.voucherPayPin.set('');
    this.voucherPayConfirmStep.set(false);
    this.voucherModalLoading.set(true);
    this.voucherModalVouchers.set([]);
    this.voucherService.getVouchers({ limit: 100 }).subscribe({
      next: (res) => {
        const eligible = (res.vouchers ?? []).filter((v) => v.currentBalance >= total);
        this.voucherModalVouchers.set(eligible);
        this.voucherModalLoading.set(false);
        if (eligible.length === 1) this.voucherPayVoucherId.set(eligible[0].id);
      },
      error: () => {
        this.voucherModalVouchers.set([]);
        this.voucherModalLoading.set(false);
      },
    });
  }

  closeVoucherPayModal(): void {
    this.voucherModalOpen.set(false);
    this.voucherPayForCart.set(false);
    this.voucherPayError.set(null);
    this.voucherPayConfirmStep.set(false);
  }

  proceedToVoucherConfirm(): void {
    const vid = this.voucherPayVoucherId();
    const pin = this.voucherPayPin().trim();
    if (!vid || !pin || pin.length < 4) {
      this.voucherPayError.set('Select a voucher and enter PIN (min 4 characters).');
      return;
    }
    this.voucherPayError.set(null);
    this.voucherPayConfirmStep.set(true);
  }

  submitVoucherPay(): void {
    if (this.voucherPayForCart()) {
      this.submitVoucherPayCart();
      return;
    }
    const b = this.bill();
    const op = this.selectedOperator();
    if (!b || !op) return;
    const amt = this.currentPayableAmount();
    const voucher_id = this.voucherPayVoucherId();
    const pin = this.voucherPayPin().trim();
    if (!voucher_id || !pin) return;
    this.voucherPaying.set(true);
    this.voucherPayError.set(null);
    const basePayload: BBPSPaymentRequest = {
      billId: b.billId,
      operatorId: b.operatorId,
      consumerId: b.consumerId,
      amount: amt,
      customerName: b.consumerName ?? 'Customer',
      customerEmail: 'customer@example.com',
      customerPhone: '9999999999',
      billDetails: Object.fromEntries((b.billDetails ?? []).map((d) => [d.label, d.value])),
      paymentMethod: 'voucher',
      voucher_id,
      pin,
    };
    this.api.payBill(basePayload).subscribe({
      next: (res) => {
        this.voucherPaying.set(false);
        if (res.success) {
          const payStatus = (res.status ?? '').toString().toUpperCase();
          const isPending =
            payStatus.includes('PENDING') ||
            payStatus.includes('SUBMITTED') ||
            payStatus.includes('INIT');
          this.closeVoucherPayModal();
          this.playBharatConnectMogo();
          if (isPending) {
            this.notification.showInfo('Payment submitted. Final confirmation is pending.');
          } else {
            this.notification.showSuccess('Bill paid successfully');
          }
          this.router.navigate(['/payment/status'], {
            queryParams: {
              status: isPending ? 'failed' : 'success',
              reason: isPending ? 'not_confirmed' : undefined,
              transactionId: res.transactionId ?? '',
              amount: amt,
            },
          });
        } else {
          this.voucherPayError.set(res.message ?? 'Payment failed');
        }
      },
      error: (err) => {
        this.voucherPaying.set(false);
        this.voucherPayError.set(err?.error?.detail ?? err?.message ?? 'Payment failed');
      },
    });
  }

  submitVoucherPayCart(): void {
    const cartItems = this.cart();
    if (cartItems.length === 0) return;
    const voucher_id = this.voucherPayVoucherId();
    const pin = this.voucherPayPin().trim();
    if (!voucher_id || !pin) return;
    this.voucherPaying.set(true);
    this.voucherPayError.set(null);
    const bills = cartItems.map((b) => ({
      billId: b.billId,
      operatorId: b.operatorId,
      consumerId: b.consumerId,
      amount: b.amount,
    }));
    this.api.payCart({ bills, voucher_id, pin }).subscribe({
      next: (res) => {
        this.voucherPaying.set(false);
        if (res.success) {
          const hasPending = (res.results ?? []).some((r) => {
            const s = (r.status ?? '').toString().toUpperCase();
            return s.includes('PENDING') || s.includes('SUBMITTED') || s.includes('INIT');
          });
          this.closeVoucherPayModal();
          this.cart.set([]);
          this.playBharatConnectMogo();
          if (hasPending) {
            this.notification.showInfo(`Cart payment submitted. ${res.results?.length ?? 0} bill(s) pending confirmation.`);
          } else {
            this.notification.showSuccess(`Cart paid successfully. ${res.results?.length ?? 0} bill(s).`);
          }
          this.router.navigate(['/payment/status'], {
            queryParams: {
              status: hasPending ? 'failed' : 'success',
              reason: hasPending ? 'not_confirmed' : undefined,
              transactionId: res.results?.[0]?.transactionId ?? '',
              amount: res.total,
            },
          });
        } else {
          this.voucherPayError.set(res.message ?? 'Payment failed');
        }
      },
      error: (err) => {
        this.voucherPaying.set(false);
        this.voucherPayError.set(err?.error?.detail ?? err?.message ?? 'Payment failed');
      },
    });
  }

  saveBillWithNickname(): void {
    const b = this.bill();
    const op = this.selectedOperator();
    const cat = this.selectedCategory();
    const nickname = this.billNickname().trim();
    if (!b || !op || !cat) return;
    if (!nickname) {
      this.notification.showError('Enter a nickname to save this bill');
      return;
    }
    this.bbpsStorage.addSavedBill({
      nickname,
      operatorId: op.id,
      operatorName: b.operatorName,
      category: cat,
      mobikwikOpId: b.mobikwikOpId ?? op.mobikwikOpId,
      consumerId: b.consumerId,
      lastAmount: this.currentPayableAmount(),
      billId: b.billId,
    });
    this.notification.showSuccess(`"${nickname}" saved. You can pay quickly from Saved bills.`);
  }

  payBill() {
    const b = this.bill();
    const op = this.selectedOperator();
    if (!b || !op) return;
    const method = this.paymentMethod();
    const amt = this.currentPayableAmount();

    const basePayload: BBPSPaymentRequest = {
      billId: b.billId,
      operatorId: b.operatorId,
      consumerId: b.consumerId,
      amount: amt,
      customerName: b.consumerName ?? 'Customer',
      customerEmail: 'customer@example.com',
      customerPhone: '9999999999',
      billDetails: Object.fromEntries((b.billDetails ?? []).map((d) => [d.label, d.value])),
      paymentMethod: method,
    };

    if (method === 'voucher') {
      this.openVoucherPayModal();
      return;
    }

    this.paying.set(true);
    this.paymentService.getAvailableGateways().subscribe({
      next: (gateways) => {
        const gateway = (gateways?.length ? gateways[0].name : 'cashfree') as 'razorpay' | 'cashfree';
        const request = {
          amount: amt,
          currency: 'INR',
          orderId: '',
          orderDescription: `BBPS bill ${b.operatorName}`,
          transactionType: 'bbps' as const,
          customer: { name: basePayload.customerName, email: basePayload.customerEmail, phone: basePayload.customerPhone },
        };
        // Cashfree uses full-page redirect; payBill runs on /payment/callback/cashfree via sessionStorage.
        try {
          sessionStorage.setItem(
            'parkpe_bbps_pending_pay',
            JSON.stringify({
              billId: basePayload.billId,
              operatorId: basePayload.operatorId,
              consumerId: basePayload.consumerId,
              amount: basePayload.amount,
              customerName: basePayload.customerName,
              customerEmail: basePayload.customerEmail,
              customerPhone: basePayload.customerPhone,
              billDetails: basePayload.billDetails ?? {},
            })
          );
        } catch {
          /* storage full / private mode */
        }
        this.paymentService.createOrderAndOpenCheckout(gateway, request, () => {}).subscribe({
          next: () => {
            /* User redirected to Cashfree; paying resets on callback or new navigation */
          },
          error: (err: Error) => {
            try {
              sessionStorage.removeItem('parkpe_bbps_pending_pay');
            } catch {
              /* ignore */
            }
            this.paying.set(false);
            this.notification.showError(err?.message ?? 'Could not start payment');
          },
        });
      },
      error: () => {
        this.paying.set(false);
        this.notification.showError('No payment gateway available');
      },
    });
  }

  startOver() {
    this.step.set('category');
    this.selectedCategory.set(null);
    this.selectedOperator.set(null);
    this.operators.set([]);
    this.bill.set(null);
    this.billForm = this.fb.group({});
  }
}
