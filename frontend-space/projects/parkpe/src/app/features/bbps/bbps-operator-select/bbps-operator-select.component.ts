import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
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
              <h3>{{ operator.name }}</h3>
              <p>{{ operator.code }}</p>
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

      h3 { font-size: 1.125rem; font-weight: 600; margin-bottom: 0.25rem; }
      p { font-size: 0.875rem; color: var(--text-secondary); }
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
}
