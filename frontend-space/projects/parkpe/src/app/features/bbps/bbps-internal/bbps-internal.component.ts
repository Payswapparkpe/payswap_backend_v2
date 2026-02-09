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
import { CommonModule } from '@angular/common';
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
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';
import {
  BBPSOperator,
  BillFetchResponse,
  BBPSParameter,
  BBPSPaymentRequest,
} from '../../../core/models/bbps.model';
import { BBPSStorageService, SavedBill, FavoriteBiller } from '../services/bbps-storage.service';
import gsap from 'gsap';
import { from } from 'rxjs';
import { concatMap, filter, map, take } from 'rxjs/operators';

type Step = 'category' | 'operator' | 'form' | 'bill' | 'pay';

/** Category groups for UI: RECHARGES, UTILITIES, FINANCE & TAXES */
const CATEGORY_GROUPS: { groupKey: string; groupLabel: string; categories: string[] }[] = [
  { groupKey: 'recharges', groupLabel: 'RECHARGES', categories: ['dth', 'subscription'] },
  {
    groupKey: 'utilities',
    groupLabel: 'UTILITIES',
    categories: ['electricity', 'water', 'gas', 'broadband', 'mobile_postpaid', 'landline', 'education'],
  },
  {
    groupKey: 'finance_taxes',
    groupLabel: 'FINANCE & TAXES',
    categories: ['loan_repayment', 'insurance', 'municipal_taxes'],
  },
];

@Component({
  selector: 'app-bbps-internal',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, StepIndicatorComponent, RouterLink],
  templateUrl: './bbps-internal.component.html',
  styleUrl: './bbps-internal.component.scss',
})
export class BBPSInternalComponent implements OnInit {
  private api = inject(API_BACKEND_TOKEN);
  private authService = inject(AuthService);
  private fb = inject(FormBuilder);
  private router = inject(Router);
  private notification = inject(NotificationService);
  private bbpsStorage = inject(BBPSStorageService);
  private paymentService = inject(PaymentGatewayService);

  @ViewChild('contentBlock') contentBlock!: ElementRef<HTMLElement>;
  @ViewChild('bbpsMogo') bbpsMogoRef!: ElementRef<HTMLAudioElement>;

  readonly stepLabels = ['Category', 'Operator', 'Consumer Details', 'Pay'];

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
  voucherBalance = signal(0);
  paymentMethod = signal<'voucher' | 'pg'>('voucher');

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
  };

  /** Categories that exist in loaded list, grouped */
  categoriesByGroup = computed(() => {
    const set = new Set(this.categories());
    return CATEGORY_GROUPS.map((g) => ({
      ...g,
      categories: g.categories.filter((c) => set.has(c)),
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
    this.bbpsStorage.toggleFavorite(opId, name ?? undefined, category ?? undefined);
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
    return cat.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
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
  }

  private buildForm(operator: BBPSOperator) {
    const group: Record<string, AbstractControl> = {};
    for (const p of operator.parameters ?? []) {
      const validators = p.required ? [Validators.required] : [];
      if (p.maxLength) validators.push(Validators.maxLength(p.maxLength));
      if (p.minLength) validators.push(Validators.minLength(p.minLength));
      group[p.name] = this.fb.control('', validators);
    }
    this.billForm = this.fb.group(group);
  }

  getFormParams(): BBPSParameter[] {
    const op = this.selectedOperator();
    return op?.parameters ?? [];
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
          this.bill.set(data);
          this.billNickname.set('');
          this.step.set('bill');
          this.loadingBill.set(false);
          this.paymentService.getVoucherBalance().subscribe({
            next: (r) => this.voucherBalance.set(r.balance ?? 0),
            error: () => this.voucherBalance.set(0),
          });
        },
        error: (err) => {
          this.loadingBill.set(false);
          const msg = err?.error?.detail || err?.message || 'Failed to fetch bill';
          this.notification.showError(typeof msg === 'string' ? msg : 'Failed to fetch bill');
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
      consumerId: b.consumerId,
      lastAmount: b.amount,
      billId: b.billId,
    });
    this.notification.showSuccess(`"${nickname}" saved. You can pay quickly from Saved bills.`);
  }

  payBill() {
    const b = this.bill();
    const op = this.selectedOperator();
    if (!b || !op) return;
    const method = this.paymentMethod();

    const basePayload: BBPSPaymentRequest = {
      billId: b.billId,
      operatorId: b.operatorId,
      consumerId: b.consumerId,
      amount: b.amount,
      customerName: b.consumerName ?? 'Customer',
      customerEmail: 'customer@example.com',
      customerPhone: '9999999999',
      billDetails: Object.fromEntries((b.billDetails ?? []).map((d) => [d.label, d.value])),
      paymentMethod: method,
    };

    if (method === 'voucher') {
      this.paying.set(true);
      this.api.payBill(basePayload).subscribe({
        next: (res) => {
          this.paying.set(false);
          if (res.success) {
            this.playBharatConnectMogo();
            this.notification.showSuccess('Bill paid successfully');
            this.paymentService.getVoucherBalance().subscribe((r) => this.voucherBalance.set(r.balance ?? 0));
            this.router.navigate(['/payment/status'], {
              queryParams: {
                status: 'success',
                transactionId: res.transactionId ?? '',
                amount: b.amount,
              },
            });
          } else {
            this.notification.showError(res.message ?? 'Payment failed');
          }
        },
        error: (err) => {
          this.paying.set(false);
          const msg = err?.error?.detail ?? err?.message ?? 'Payment failed';
          this.notification.showError(typeof msg === 'string' ? msg : 'Payment failed');
        },
      });
      return;
    }

    this.paying.set(true);
    this.paymentService.getAvailableGateways().subscribe({
      next: (gateways) => {
        const gateway = (gateways?.length ? gateways[0].name : 'cashfree') as 'razorpay' | 'cashfree';
        const request = {
          amount: b.amount,
          currency: 'INR',
          orderId: '',
          orderDescription: `BBPS bill ${b.operatorName}`,
          transactionType: 'bbps' as const,
          customer: { name: basePayload.customerName, email: basePayload.customerEmail, phone: basePayload.customerPhone },
        };
        this.paymentService.createOrderAndOpenCheckout(gateway, request, (response) => {
          const payload: BBPSPaymentRequest = {
            ...basePayload,
            paymentMethod: 'pg',
            orderId: response?.orderId ?? response?.razorpay_order_id,
            paymentId: response?.paymentId ?? response?.razorpay_payment_id,
            gateway,
          };
          this.api.payBill(payload).subscribe({
            next: (res) => {
              this.paying.set(false);
              if (res.success) {
                this.playBharatConnectMogo();
                this.notification.showSuccess('Bill paid successfully');
                this.router.navigate(['/payment/status'], {
                  queryParams: {
                    status: 'success',
                    transactionId: res.transactionId ?? '',
                    amount: b.amount,
                  },
                });
              } else {
                this.notification.showError(res.message ?? 'Payment failed');
              }
            },
            error: (err) => {
              this.paying.set(false);
              const msg = err?.error?.detail ?? err?.message ?? 'Payment failed';
              this.notification.showError(typeof msg === 'string' ? msg : 'Payment failed');
            },
          });
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
