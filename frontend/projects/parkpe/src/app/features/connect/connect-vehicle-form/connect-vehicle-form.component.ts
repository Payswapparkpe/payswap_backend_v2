import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ConnectService, ConnectVehicle, ConnectVehicleCreate, ConnectVehiclesMeta } from '../services/connect.service';
import { MobilityStateStore } from '../../../core/stores/mobility-state.store';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import type { ApiBackend } from '../../../core/api/api-backend.interface';
import type { BBPSOperator } from '../../../core/models/bbps.model';
import {
  VEHICLE_TYPES,
  getBrandsForType,
  getModelsForBrand,
  type VehicleTypeId,
} from '../data/vehicle-types-data';

const OTHER = 'Other';

/** Legal ownership declaration text – vehicle belongs to user/family; user takes responsibility; company may take legal action. */
export const VEHICLE_OWNERSHIP_DECLARATION = `I declare that this vehicle belongs to me or my immediate family. I take full responsibility for the accuracy of the details provided and for any use of the vehicle in connection with ParkPe Connect. I understand that the company may take legal action for misuse or misrepresentation. I confirm that the information I have provided is correct to the best of my knowledge.`;

@Component({
  selector: 'app-connect-vehicle-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  templateUrl: './connect-vehicle-form.component.html',
  styleUrl: './connect-vehicle-form.component.scss',
})
export class ConnectVehicleFormComponent implements OnInit {
  private fb = inject(FormBuilder);
  private connect = inject(ConnectService);
  private api = inject(API_BACKEND_TOKEN) as ApiBackend;
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private mobilityStore = inject(MobilityStateStore);

  readonly vehicleTypes = VEHICLE_TYPES;
  readonly declarationText = VEHICLE_OWNERSHIP_DECLARATION;
  isEdit = signal(false);
  vehicleId = signal<number | null>(null);
  loading = signal(false);
  error = signal<string | null>(null);
  connectMeta = signal<ConnectVehiclesMeta | null>(null);
  fastagOperators = signal<BBPSOperator[]>([]);

  form = this.fb.nonNullable.group({
    vehicle_type: ['' as VehicleTypeId | '', []],
    registration_number: ['', [Validators.required, Validators.maxLength(32)]],
    brand: [''],
    brand_other: [''],
    model: [''],
    model_other: [''],
    year: [null as number | null, []],
    is_primary: [false],
    fastag_biller_id: [''],
    accept_ownership_declaration: [false, [Validators.requiredTrue]],
  });

  /** Reactive signals so computed lists update when type/brand change (form value is not reactive). */
  selectedVehicleType = signal<VehicleTypeId | ''>('');
  selectedBrand = signal('');

  /** Brands for selected vehicle type (plus Other) */
  brandsList = computed(() => {
    const type = this.selectedVehicleType();
    if (!type) return [] as string[];
    const list = getBrandsForType(type);
    return list.length ? [...list, OTHER] : [OTHER];
  });

  /** Models for selected brand (plus Other) */
  modelsList = computed(() => {
    const type = this.selectedVehicleType();
    const brand = this.selectedBrand();
    if (!type || !brand || brand === OTHER) return [] as string[];
    const list = getModelsForBrand(type, brand);
    return list.length ? [...list, OTHER] : [OTHER];
  });

  showBrandOther = computed(() => this.form.getRawValue().brand === OTHER);
  showModelOther = computed(() => this.form.getRawValue().model === OTHER);

  /** Car / CV — FASTag issuer applies */
  isFastagVehicleType = computed(() => {
    const t = this.selectedVehicleType();
    return t === 'four_wheeler' || t === 'commercial';
  });

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      const n = parseInt(id, 10);
      if (!isNaN(n)) {
        this.isEdit.set(true);
        this.vehicleId.set(n);
        this.connect.getVehicle(n).subscribe({
          next: (v) => {
            const rawType = v.vehicle_type || '';
            const type: VehicleTypeId | '' = rawType === 'three_wheeler' ? 'commercial' : (rawType as VehicleTypeId) || '';
            const brands = type ? getBrandsForType(type) : [];
            const brandInList = v.brand && brands.includes(v.brand);
            const models = type && v.brand && v.brand !== OTHER ? getModelsForBrand(type, v.brand) : [];
            const modelInList = v.model && models.includes(v.model);
            this.form.patchValue({
              vehicle_type: type,
              registration_number: v.registration_number,
              brand: brandInList ? v.brand! : (v.brand ? OTHER : ''),
              brand_other: brandInList ? '' : (v.brand || ''),
              model: modelInList ? v.model! : (v.model ? OTHER : ''),
              model_other: modelInList ? '' : (v.model || ''),
              year: v.year,
              is_primary: v.is_primary,
              fastag_biller_id: v.fastag_biller_id || '',
              accept_ownership_declaration: true,
            });
            this.selectedVehicleType.set(type);
            this.selectedBrand.set(brandInList ? v.brand! : (v.brand ? OTHER : ''));
            this.updateBrandModelDisabled();
            if (type === 'four_wheeler' || type === 'commercial') {
              this.loadFastagOperators();
            }
          },
          error: () => this.error.set('Vehicle not found'),
        });
      }
    } else {
      // When adding: default primary if no vehicles; check can_add_more for limit
      this.connect.getVehicles().subscribe({
        next: (res) => {
          const list = res.results ?? [];
          if (list.length === 0) this.form.patchValue({ is_primary: true });
          this.connectMeta.set(res.meta ?? null);
        },
      });
      this.updateBrandModelDisabled();
    }
  }

  /** Update brand/model control disabled state (use FormControl.enable/disable to avoid template disabled warning). */
  private updateBrandModelDisabled() {
    const type = this.selectedVehicleType();
    const brand = this.selectedBrand();
    if (!type) {
      this.form.get('brand')?.disable({ emitEvent: false });
      this.form.get('model')?.disable({ emitEvent: false });
    } else {
      this.form.get('brand')?.enable({ emitEvent: false });
      if (!brand) {
        this.form.get('model')?.disable({ emitEvent: false });
      } else {
        this.form.get('model')?.enable({ emitEvent: false });
      }
    }
  }

  onVehicleTypeChange() {
    const type = this.form.getRawValue().vehicle_type as VehicleTypeId | '';
    this.selectedVehicleType.set(type);
    this.selectedBrand.set('');
    this.form.patchValue({ brand: '', brand_other: '', model: '', model_other: '', fastag_biller_id: '' });
    this.updateBrandModelDisabled();
    if (type === 'four_wheeler' || type === 'commercial') {
      this.loadFastagOperators();
    }
  }

  private loadFastagOperators(): void {
    this.api.getOperators('fastag').subscribe({
      next: (ops) => this.fastagOperators.set(ops ?? []),
      error: () => this.fastagOperators.set([]),
    });
  }

  onBrandChange() {
    this.selectedBrand.set(this.form.getRawValue().brand || '');
    this.form.patchValue({ model: '', model_other: '' });
    this.updateBrandModelDisabled();
  }

  submit() {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    const raw = this.form.getRawValue();
    const brand = raw.brand === OTHER ? (raw.brand_other || '').trim() : (raw.brand || '').trim();
    const model = raw.model === OTHER ? (raw.model_other || '').trim() : (raw.model || '').trim();
    const payload: ConnectVehicleCreate = {
      vehicle_type: (raw.vehicle_type || undefined) as string | undefined,
      registration_number: raw.registration_number.trim(),
      brand: brand || undefined,
      model: model || undefined,
      year: raw.year ?? undefined,
      is_primary: raw.is_primary,
    };
    const vt = raw.vehicle_type;
    if (vt === 'four_wheeler' || vt === 'commercial') {
      payload.fastag_biller_id = (raw.fastag_biller_id || '').trim();
    }
    if (!this.isEdit()) {
      payload.accept_ownership_declaration = raw.accept_ownership_declaration;
    }

    const id = this.vehicleId();
    if (this.isEdit() && id != null) {
      this.connect.updateVehicle(id, payload).subscribe({
        next: (updated) => {
          this.loading.set(false);
          this.mergeVehicleIntoStore(updated);
          this.mobilityStore.notifyConnectVehicleListChanged();
          this.router.navigate(['/connect/vehicles']);
        },
        error: (err) => {
          this.error.set(err?.error?.detail || 'Update failed');
          this.loading.set(false);
        },
      });
    } else {
      this.connect.createVehicle(payload).subscribe({
        next: (v) => {
          this.loading.set(false);
          this.mergeVehicleIntoStore(v);
          this.mobilityStore.notifyConnectVehicleListChanged();
          this.router.navigate(['/connect/vehicles', v.id]);
        },
        error: (err) => {
          const body = err?.error || {};
          this.error.set(body.detail || 'Create failed');
          this.loading.set(false);
        },
      });
    }
  }

  /** Keep MobilityStateStore in sync so dashboard / cached views update without a full reload. */
  private mergeVehicleIntoStore(v: ConnectVehicle): void {
    const normalized: ConnectVehicle = { ...v, rc_data: v.vehicle_rc ?? v.rc_data };
    const cur = this.mobilityStore.connectVehicles();
    const idx = cur.findIndex((x) => x.id === v.id);
    const next =
      idx >= 0 ? cur.map((x, i) => (i === idx ? normalized : x)) : [...cur, normalized];
    this.mobilityStore.setConnectVehicles(next);
  }
}
