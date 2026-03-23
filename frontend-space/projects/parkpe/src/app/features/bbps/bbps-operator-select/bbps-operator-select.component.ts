import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { environment } from '../../../../environments/environment';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { BBPSOperator } from '../../../core/models/bbps.model';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

@Component({
  selector: 'app-bbps-operator-select',
  standalone: true,
  imports: [CommonModule, StepIndicatorComponent],
  template: `
    <div class="feature-container">
      <app-step-indicator [steps]="stepLabels" [currentStep]="2" />
      <button class="btn btn-outline back-btn" (click)="goBack()">
        <span class="material-icons">arrow_back</span> Back
      </button>

      <h1 class="feature-title">Select {{ category | titlecase }} Operator</h1>
      
      @if (loading) {
        <div class="loading-state"><div class="spinner"></div></div>
      } @else {
        <div class="operators-list">
          @for (operator of operators; track operator.id) {
            <div class="operator-card card" (click)="selectOperator(operator)">
              <div class="operator-head">
                <img class="operator-icon" [src]="getOperatorIconUrl(operator)" [alt]="operator.name" loading="lazy" />
                <div>
                  <h3>{{ operator.name }}</h3>
                  <p>{{ operator.code }}</p>
                </div>
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 800px; margin: 0 auto; }
    .back-btn { margin-bottom: 1rem; display: inline-flex; align-items: center; gap: 0.5rem; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; }
    .operators-list { display: flex; flex-direction: column; gap: 1rem; }
    .operator-card {
      padding: 1.5rem;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        box-shadow: var(--shadow-green-md);
        transform: translateX(4px);
      }

      h3 { font-size: 0.92rem; font-weight: 600; margin-bottom: 0.2rem; line-height: 1.25; }
      p { font-size: 0.74rem; color: var(--text-secondary); }
    }
    .operator-head { display: flex; align-items: center; gap: 0.75rem; }
    .operator-icon {
      width: 4rem;
      height: 2rem;
      border-radius: 0.4rem;
      object-fit: contain;
      border: 1px solid var(--border-light);
      background: #fff;
      padding: 0.16rem;
      image-rendering: -webkit-optimize-contrast;
      flex-shrink: 0;
    }
  `],
})
export class BBPSOperatorSelectComponent implements OnInit {
  readonly stepLabels = ['Category', 'Operator', 'Fetch Bill', 'Pay'];
  private api = inject(API_BACKEND_TOKEN);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  category = '';
  operators: BBPSOperator[] = [];
  loading = true;

  private readonly mobikwikOperatorIconBase = environment.mobikwikIconBase;

  ngOnInit() {
    this.category = this.route.snapshot.params['category'];
    this.api.getOperators(this.category).subscribe({
      next: (data) => {
        this.operators = data;
        this.loading = false;
      },
    });
  }

  selectOperator(operator: BBPSOperator) {
    this.router.navigate(['/bbps/bill'], { state: { operator } });
  }

  goBack() {
    this.router.navigate(['/bbps/category']);
  }

  getOperatorIconUrl(operator?: BBPSOperator | null): string {
    const explicitLogo = (operator?.logo ?? '').toString().trim();
    if (explicitLogo && !explicitLogo.includes('bharat-connect-logo')) {
      return explicitLogo;
    }
    const candidates = [operator?.mobikwikOpId];
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
}
