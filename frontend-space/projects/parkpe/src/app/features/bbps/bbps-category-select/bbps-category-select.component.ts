import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { StepIndicatorComponent } from '../../../shared/components/step-indicator/step-indicator.component';

@Component({
  selector: 'app-bbps-category-select',
  standalone: true,
  imports: [CommonModule, StepIndicatorComponent],
  template: `
    <div class="feature-container">
      <app-step-indicator [steps]="stepLabels" [currentStep]="1" />
      <h1 class="feature-title">Select Bill Category</h1>
      
      @if (loading) {
        <div class="loading-state">
          <div class="spinner"></div>
        </div>
      } @else {
        <div class="categories-grid">
          @for (category of categories; track category) {
            <div class="category-card card" (click)="selectCategory(category)">
              <div class="category-icon">
                <span class="material-icons">{{ getCategoryIcon(category) }}</span>
              </div>
              <h3>{{ getCategoryLabel(category) }}</h3>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .feature-container { padding: 2rem; max-width: 1000px; margin: 0 auto; }
    .feature-title { font-size: 2rem; font-weight: 700; margin-bottom: 2rem; color: var(--text-primary); }
    .categories-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 1.5rem;
    }
    .category-card {
      text-align: center;
      padding: 2rem 1rem;
      cursor: pointer;
      transition: all 0.3s ease;

      &:hover {
        transform: translateY(-5px);
        box-shadow: var(--shadow-green-lg);
      }
    }
    .category-icon {
      width: 60px;
      height: 60px;
      margin: 0 auto 1rem;
      background: var(--primary-100);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;

      .material-icons {
        font-size: 32px;
        color: var(--primary-600);
      }
    }
    h3 { font-size: 1rem; font-weight: 600; color: var(--text-primary); }
  `],
})
export class BBPSCategorySelectComponent implements OnInit {
  readonly stepLabels = ['Category', 'Operator', 'Fetch Bill', 'Pay'];
  private api = inject(API_BACKEND_TOKEN);
  private router = inject(Router);

  categories: string[] = [];
  loading = true;

  ngOnInit() {
    this.api.getCategories().subscribe({
      next: (data) => {
        this.categories = data;
        this.loading = false;
      },
    });
  }

  selectCategory(category: string) {
    this.router.navigate(['/bbps/operator', category]);
  }

  getCategoryIcon(category: string): string {
    const icons: Record<string, string> = {
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
    };
    return icons[category] || 'receipt';
  }

  getCategoryLabel(category: string): string {
    return category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
}
