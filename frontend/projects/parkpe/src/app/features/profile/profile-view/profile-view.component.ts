import { Component, inject, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';
import { User } from 'shared';

type ProfileTab = 'overview' | 'personal' | 'address' | 'preferences';

@Component({
  selector: 'app-profile-view',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  template: `
    <div class="ph-root">
      <!-- ── Loading ── -->
      @if (loading()) {
        <div class="ph-loading">
          <div class="ph-spinner"></div>
          <p>Loading your profile…</p>
        </div>
      } @else if (error()) {
        <div class="ph-error card">
          <span class="mi">error_outline</span>
          <p>{{ error() }}</p>
          <button class="btn btn-primary" (click)="load()">Retry</button>
        </div>
      } @else {
        <!-- ── HERO CARD ── -->
        <div class="ph-hero">
          <div class="ph-hero-glow"></div>
          <div class="ph-hero-inner">
            <div class="ph-avatar-wrap">
              <div class="ph-avatar">{{ initials() }}</div>
              @if (user()?.emailVerified || user()?.phoneVerified) {
                <div class="ph-avatar-badge" title="Verified"><span class="mi mi-sm">verified</span></div>
              }
            </div>
            <div class="ph-hero-info">
              <h1>{{ user()?.name || 'ParkPe User' }}</h1>
              <p class="ph-sub">{{ user()?.email }}</p>
              @if (user()?.phone) { <p class="ph-sub ph-sub--phone">{{ user()?.phone }}</p> }
              <div class="ph-chips">
                <span class="chip chip--blue"><span class="mi mi-sm">directions_car</span>ParkPe Customer</span>
                @if (user()?.emailVerified) {
                  <span class="chip chip--green"><span class="mi mi-sm">mark_email_read</span>Email verified</span>
                }
                @if (user()?.phoneVerified) {
                  <span class="chip chip--green"><span class="mi mi-sm">smartphone</span>Phone verified</span>
                }
              </div>
            </div>
            <div class="ph-hero-comp">
              <div class="ph-comp-nums">
                <span class="ph-comp-pct">{{ completionPct() }}<small>%</small></span>
                <span class="ph-comp-lbl">Profile complete</span>
              </div>
              <div class="ph-bar-track">
                <div class="ph-bar-fill" [style.width.%]="completionPct()"></div>
              </div>
              @if (missingCount() > 0) {
                <p class="ph-missing">{{ missingCount() }} items incomplete</p>
              } @else {
                <p class="ph-complete-txt"><span class="mi mi-sm">check_circle</span> All done!</p>
              }
            </div>
          </div>
        </div>

        <!-- ── TAB BAR ── -->
        <div class="ph-tabs">
          @for (t of tabs; track t.id) {
            <button
              class="ph-tab"
              [class.ph-tab--active]="activeTab() === t.id"
              (click)="setTab(t.id)"
              type="button"
            >
              <span class="mi">{{ t.icon }}</span>
              {{ t.label }}
            </button>
          }
        </div>

        <!-- ── TAB CONTENT ── -->
        <div class="ph-body">

          <!-- OVERVIEW -->
          @if (activeTab() === 'overview') {
            <div class="ph-overview">

              <!-- Stats row -->
              <div class="stat-row">
                <div class="stat-card">
                  <span class="mi stat-icon stat-icon--blue">calendar_today</span>
                  <div>
                    <p class="stat-val">{{ user()?.createdAt | date:'MMM yyyy' }}</p>
                    <p class="stat-lbl">Member since</p>
                  </div>
                </div>
                <div class="stat-card">
                  <span class="mi stat-icon" [class.stat-icon--green]="user()?.emailVerified" [class.stat-icon--red]="!user()?.emailVerified">
                    {{ user()?.emailVerified ? 'mark_email_read' : 'email' }}
                  </span>
                  <div>
                    <p class="stat-val">{{ user()?.emailVerified ? 'Verified' : 'Unverified' }}</p>
                    <p class="stat-lbl">Email status</p>
                  </div>
                </div>
                <div class="stat-card">
                  <span class="mi stat-icon" [class.stat-icon--green]="user()?.phoneVerified" [class.stat-icon--red]="!user()?.phoneVerified">
                    {{ user()?.phoneVerified ? 'smartphone' : 'phone_iphone' }}
                  </span>
                  <div>
                    <p class="stat-val">{{ user()?.phoneVerified ? 'Verified' : 'Unverified' }}</p>
                    <p class="stat-lbl">Phone status</p>
                  </div>
                </div>
                <div class="stat-card">
                  <span class="mi stat-icon" [class.stat-icon--green]="user()?.billingAddressComplete" [class.stat-icon--amber]="!user()?.billingAddressComplete">
                    {{ user()?.billingAddressComplete ? 'home' : 'home_work' }}
                  </span>
                  <div>
                    <p class="stat-val">{{ user()?.billingAddressComplete ? 'Complete' : 'Incomplete' }}</p>
                    <p class="stat-lbl">Billing address</p>
                  </div>
                </div>
              </div>

              <!-- Checklist + quick actions -->
              <div class="ph-card-grid">
                <div class="info-card">
                  <div class="info-card-head">
                    <span class="mi">checklist</span>
                    <h3>Completion Checklist</h3>
                  </div>
                  <div class="checklist">
                    @for (item of completionChecklist(); track item.label) {
                      <div class="check-row" [class.check-row--done]="item.done">
                        <span class="mi mi-sm">{{ item.done ? 'check_circle' : 'radio_button_unchecked' }}</span>
                        <span>{{ item.label }}</span>
                        @if (!item.done) {
                          <button class="check-link" (click)="setTab(item.tab)" type="button">Fix →</button>
                        }
                      </div>
                    }
                  </div>
                </div>

                <div class="info-card">
                  <div class="info-card-head">
                    <span class="mi">bolt</span>
                    <h3>Quick Actions</h3>
                  </div>
                  <div class="quick-actions">
                    <button class="qa-item" (click)="setTab('personal')" type="button">
                      <span class="qa-icon"><span class="mi">person</span></span>
                      <div><strong>Personal Info</strong><p>Name & mobile</p></div>
                      <span class="mi qa-arrow">chevron_right</span>
                    </button>
                    <button class="qa-item" (click)="setTab('address')" type="button">
                      <span class="qa-icon"><span class="mi">location_on</span></span>
                      <div><strong>Address</strong><p>Delivery & billing address</p></div>
                      <span class="mi qa-arrow">chevron_right</span>
                    </button>
                    <button class="qa-item" (click)="setTab('preferences')" type="button">
                      <span class="qa-icon"><span class="mi">tune</span></span>
                      <div><strong>Preferences</strong><p>Language, notifications</p></div>
                      <span class="mi qa-arrow">chevron_right</span>
                    </button>
                    <a class="qa-item" routerLink="/settings">
                      <span class="qa-icon"><span class="mi">lock</span></span>
                      <div><strong>Security</strong><p>Password, PIN, passkeys</p></div>
                      <span class="mi qa-arrow">chevron_right</span>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          }

          <!-- PERSONAL INFO -->
          @if (activeTab() === 'personal') {
            <form [formGroup]="personalForm" (ngSubmit)="savePersonal()" class="ph-form card">
              <h3 class="ph-form-title">Personal Information</h3>
              <div class="ph-form-grid">
                <div class="ph-field">
                  <label for="pf-name">Full Name</label>
                  <input id="pf-name" formControlName="name" type="text" class="ph-input" placeholder="Your full name" />
                  @if (personalForm.get('name')?.invalid && personalForm.get('name')?.touched) {
                    <span class="ph-err">Name is required</span>
                  }
                </div>
                <div class="ph-field">
                  <label for="pf-phone">Mobile Number</label>
                  <input id="pf-phone" formControlName="phone" type="tel" class="ph-input" placeholder="10-digit mobile" />
                  @if (personalForm.get('phone')?.invalid && personalForm.get('phone')?.touched) {
                    <span class="ph-err">Enter a valid mobile number</span>
                  }
                </div>
                <div class="ph-field">
                  <label for="pf-email">Email</label>
                  <input id="pf-email" formControlName="email" type="email" class="ph-input ph-input--disabled" [attr.disabled]="true" />
                  <span class="ph-hint">Email cannot be changed from here</span>
                </div>
              </div>
              <div class="ph-form-actions">
                <button type="submit" class="btn btn-primary" [disabled]="savingPersonal()">
                  @if (savingPersonal()) { <span class="ph-spinner ph-spinner--sm"></span> Saving… }
                  @else { Save Personal Info }
                </button>
              </div>
            </form>
          }

          <!-- ADDRESS -->
          @if (activeTab() === 'address') {
            <form [formGroup]="addressForm" (ngSubmit)="saveAddress()" class="ph-form card">
              <h3 class="ph-form-title">Address Details</h3>
              <div class="ph-form-grid">
                <div class="ph-field ph-field--full">
                  <label for="pf-addr1">Address Line 1</label>
                  <input id="pf-addr1" formControlName="addressLine1" type="text" class="ph-input" placeholder="House/flat, street" />
                </div>
                <div class="ph-field ph-field--full">
                  <label for="pf-addr2">Address Line 2 <span class="ph-opt">(optional)</span></label>
                  <input id="pf-addr2" formControlName="addressLine2" type="text" class="ph-input" placeholder="Landmark, area" />
                </div>
                <div class="ph-field">
                  <label for="pf-pincode">Pincode</label>
                  <div class="ph-pinrow">
                    <input id="pf-pincode" formControlName="pincode" type="text" class="ph-input" placeholder="6-digit PIN" maxlength="6" />
                    <button type="button" class="btn btn-outline ph-lookup-btn" (click)="lookupPincode()" [disabled]="lookingUpPin()">
                      @if (lookingUpPin()) { … } @else { Lookup }
                    </button>
                  </div>
                </div>
                <div class="ph-field">
                  <label for="pf-city">City</label>
                  <input id="pf-city" formControlName="city" type="text" class="ph-input" placeholder="City" />
                </div>
                <div class="ph-field">
                  <label for="pf-state">State</label>
                  <input id="pf-state" formControlName="state" type="text" class="ph-input" placeholder="State" />
                </div>
                <div class="ph-field">
                  <label for="pf-country">Country</label>
                  <input id="pf-country" formControlName="countryOfResidence" type="text" class="ph-input" placeholder="Country" />
                </div>
              </div>
              <div class="ph-form-actions">
                <button type="submit" class="btn btn-primary" [disabled]="savingAddress()">
                  @if (savingAddress()) { <span class="ph-spinner ph-spinner--sm"></span> Saving… }
                  @else { Save Address }
                </button>
              </div>
            </form>
          }

          <!-- PREFERENCES -->
          @if (activeTab() === 'preferences') {
            <form [formGroup]="prefsForm" (ngSubmit)="savePrefs()" class="ph-form card">
              <h3 class="ph-form-title">Preferences</h3>
              <div class="ph-form-grid">
                <div class="ph-field">
                  <label for="pf-lang">Language</label>
                  <select id="pf-lang" formControlName="languagePreference" class="ph-input">
                    <option value="en">English</option>
                    <option value="hi">Hindi</option>
                  </select>
                </div>
                <div class="ph-field">
                  <label for="pf-tz">Timezone</label>
                  <input id="pf-tz" formControlName="timezone" type="text" class="ph-input" placeholder="e.g. Asia/Kolkata" />
                </div>
                <div class="ph-field">
                  <label for="pf-currency">Currency</label>
                  <select id="pf-currency" formControlName="currencyPreference" class="ph-input">
                    <option value="INR">INR (₹)</option>
                    <option value="USD">USD ($)</option>
                  </select>
                </div>
              </div>
              <div class="ph-notif">
                <h4>Notification Preferences</h4>
                <div class="ph-toggle-grid">
                  @for (n of notifToggles; track n.key) {
                    <label class="ph-toggle">
                      <input type="checkbox" [formControlName]="n.key" />
                      <span class="ph-toggle-track"></span>
                      {{ n.label }}
                    </label>
                  }
                </div>
              </div>
              <div class="ph-form-actions">
                <button type="submit" class="btn btn-primary" [disabled]="savingPrefs()">
                  @if (savingPrefs()) { <span class="ph-spinner ph-spinner--sm"></span> Saving… }
                  @else { Save Preferences }
                </button>
              </div>
            </form>
          }


        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }
    .ph-root {
      padding: clamp(.75rem, 2vw, 1.5rem);
      max-width: 860px;
      margin: 0 auto;
      display: grid;
      gap: 1rem;
    }

    /* ── Loading / Error ── */
    .ph-loading, .ph-error {
      display: grid; place-items: center; gap: .75rem;
      text-align: center; min-height: 200px; padding: 2rem;
      background:#fff; border-radius:1.25rem; border:1px solid #e2e8f0;
    }
    .ph-spinner {
      width: 36px; height: 36px; border-radius: 50%;
      border: 3px solid rgba(37,99,235,.18);
      border-top-color: #2563eb;
      animation: spin .75s linear infinite;
    }
    .ph-spinner--sm { width:15px; height:15px; border-width:2px; display:inline-block; vertical-align:middle; margin-right:5px; }
    @keyframes spin { to { transform:rotate(360deg); } }

    /* ── Hero ── */
    .ph-hero {
      position: relative; overflow: hidden;
      border-radius: 1.35rem;
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 55%, #3b82f6 100%);
      padding: 1.6rem 1.6rem 1.4rem;
      box-shadow: 0 8px 32px rgba(37,99,235,.22);
    }
    .ph-hero-glow {
      position:absolute; inset:0; pointer-events:none;
      background: radial-gradient(ellipse 70% 60% at 85% -20%, rgba(255,255,255,.18), transparent 65%),
                  radial-gradient(ellipse 40% 40% at 15% 110%, rgba(96,165,250,.25), transparent 60%);
    }
    .ph-hero-inner {
      position: relative; z-index:1;
      display: flex; align-items: flex-start; gap: 1.1rem; flex-wrap: wrap;
    }
    .ph-avatar-wrap { position:relative; flex-shrink:0; }
    .ph-avatar {
      width:70px; height:70px; border-radius:20px;
      background: rgba(255,255,255,.2);
      backdrop-filter: blur(12px);
      border: 2px solid rgba(255,255,255,.4);
      display:flex; align-items:center; justify-content:center;
      color:#fff; font-size:1.5rem; font-weight:900;
      letter-spacing:-.02em;
      box-shadow: 0 6px 20px rgba(0,0,0,.18);
    }
    .ph-avatar-badge {
      position:absolute; bottom:-4px; right:-4px;
      width:22px; height:22px; border-radius:50%;
      background:#22c55e; border:2px solid #fff;
      display:flex; align-items:center; justify-content:center;
      box-shadow:0 2px 6px rgba(0,0,0,.18);
    }
    .ph-avatar-badge .mi { color:#fff; font-size:12px; line-height:1; }
    .ph-hero-info { flex:1; min-width:200px; }
    .ph-hero-info h1 { margin:0 0 .2rem; font-size:clamp(1.2rem,2.5vw,1.55rem); font-weight:800; color:#fff; letter-spacing:-.025em; }
    .ph-sub { color:rgba(255,255,255,.75); font-size:.84rem; margin:0 0 .1rem; }
    .ph-sub--phone { font-size:.82rem; margin-bottom:.45rem; }
    .ph-chips { display:flex; flex-wrap:wrap; gap:.3rem; margin-top:.35rem; }
    .chip {
      font-size:.72rem; border-radius:999px; padding:.22rem .6rem;
      font-weight:700; display:inline-flex; align-items:center; gap:.25rem;
    }
    .chip--green { background:rgba(34,197,94,.2); color:#86efac; border:1px solid rgba(34,197,94,.35); }
    .chip--blue  { background:rgba(255,255,255,.18); color:#fff; border:1px solid rgba(255,255,255,.3); }
    .chip--amber { background:rgba(251,191,36,.2); color:#fde68a; border:1px solid rgba(251,191,36,.3); }
    .ph-hero-comp { flex-shrink:0; min-width:160px; text-align:right; }
    .ph-comp-nums { margin-bottom:.5rem; }
    .ph-comp-pct { font-size:2.1rem; font-weight:900; color:#fff; line-height:1; }
    .ph-comp-pct small { font-size:1rem; font-weight:700; }
    .ph-comp-lbl { display:block; font-size:.76rem; color:rgba(255,255,255,.65); margin-top:.1rem; }
    .ph-bar-track { height:6px; background:rgba(255,255,255,.25); border-radius:999px; overflow:hidden; margin-bottom:.35rem; }
    .ph-bar-fill  { height:100%; background:#fff; border-radius:999px; transition:width .6s cubic-bezier(.34,1.56,.64,1); }
    .ph-missing { color:rgba(255,200,100,.9); font-size:.75rem; font-weight:600; margin:0; }
    .ph-complete-txt { color:rgba(134,239,172,.9); font-size:.75rem; font-weight:600; margin:0; display:flex; align-items:center; gap:.25rem; justify-content:flex-end; }

    /* ── Tab bar ── */
    .ph-tabs {
      display:flex; flex-wrap:wrap; gap:.35rem;
      background:#fff; border:1px solid #e2e8f0;
      border-radius:1rem; padding:.6rem .7rem;
      box-shadow:0 1px 4px rgba(0,0,0,.04);
    }
    .ph-tab {
      background:none; border:1.5px solid transparent;
      border-radius:.625rem; padding:.42rem .85rem;
      font-size:.82rem; font-weight:600; cursor:pointer;
      display:inline-flex; align-items:center; gap:.3rem;
      color:#64748b;
      transition: background .15s, color .15s, border-color .15s;
    }
    .ph-tab:hover { background:#f1f5f9; color:#1e293b; }
    .ph-tab--active {
      background: linear-gradient(135deg,#2563eb,#1d4ed8);
      color:#fff; border-color:#2563eb;
      box-shadow:0 3px 10px rgba(37,99,235,.3);
    }
    .ph-tab .mi { font-size:16px; }

    /* ── Overview ── */
    .ph-overview { display:grid; gap:.85rem; }

    /* Stats row */
    .stat-row {
      display:grid; grid-template-columns:repeat(4,1fr); gap:.7rem;
    }
    @media (max-width:700px) { .stat-row { grid-template-columns:repeat(2,1fr); } }
    @media (max-width:420px) { .stat-row { grid-template-columns:1fr; } }
    .stat-card {
      background:#fff; border:1px solid #e8edf3; border-radius:1rem;
      padding:.9rem 1rem; display:flex; align-items:center; gap:.65rem;
      transition:box-shadow .15s;
    }
    .stat-card:hover { box-shadow:0 4px 14px rgba(0,0,0,.07); }
    .stat-icon {
      font-size:1.5rem; width:40px; height:40px; border-radius:.75rem;
      display:flex; align-items:center; justify-content:center; flex-shrink:0;
    }
    .stat-icon--blue  { background:#eff6ff; color:#2563eb; }
    .stat-icon--green { background:#f0fdf4; color:#16a34a; }
    .stat-icon--red   { background:#fef2f2; color:#dc2626; }
    .stat-icon--amber { background:#fffbeb; color:#d97706; }
    .stat-val  { margin:0; font-size:.88rem; font-weight:700; color:#1e293b; }
    .stat-lbl  { margin:.1rem 0 0; font-size:.73rem; color:#64748b; }

    /* Card grid */
    .ph-card-grid { display:grid; grid-template-columns:1fr 1fr; gap:.85rem; }
    @media (max-width:640px) { .ph-card-grid { grid-template-columns:1fr; } }

    .info-card {
      background:#fff; border:1px solid #e8edf3; border-radius:1rem;
      padding:1rem 1.1rem;
    }
    .info-card-head {
      display:flex; align-items:center; gap:.45rem; margin-bottom:.75rem;
    }
    .info-card-head .mi { font-size:18px; color:#2563eb; }
    .info-card h3 { margin:0; font-size:.9rem; font-weight:800; color:#1e293b; }

    /* Checklist */
    .checklist { display:grid; gap:.35rem; }
    .check-row {
      display:flex; align-items:center; gap:.45rem;
      font-size:.83rem; color:#64748b; padding:.3rem 0;
      border-bottom:1px solid #f8fafc;
    }
    .check-row:last-child { border-bottom:none; }
    .check-row--done { color:#15803d; }
    .check-row .mi-sm { font-size:16px; color:#cbd5e1; }
    .check-row--done .mi-sm { color:#22c55e; }
    .check-link {
      margin-left:auto; font-size:.76rem; color:#2563eb;
      background:none; border:none; cursor:pointer; font-weight:700;
      padding:.15rem .35rem; border-radius:.4rem;
    }
    .check-link:hover { background:#eff6ff; }

    /* Quick actions */
    .quick-actions { display:grid; gap:.35rem; }
    .qa-item {
      display:flex; align-items:center; gap:.65rem;
      background:none; border:none; width:100%; text-align:left;
      padding:.55rem .5rem; border-radius:.75rem; cursor:pointer;
      text-decoration:none; color:inherit;
      transition:background .12s;
    }
    .qa-item:hover { background:#f8fafc; }
    .qa-icon {
      width:34px; height:34px; border-radius:.6rem;
      background:#eff6ff; display:flex; align-items:center; justify-content:center;
      flex-shrink:0;
    }
    .qa-icon .mi { font-size:18px; color:#2563eb; }
    .qa-item strong { display:block; font-size:.84rem; font-weight:700; color:#1e293b; }
    .qa-item p { margin:0; font-size:.75rem; color:#94a3b8; }
    .qa-arrow { font-size:18px; color:#cbd5e1; margin-left:auto; }

    /* ── Forms ── */
    .ph-form {
      background:#fff; border:1px solid #e8edf3; border-radius:1rem; padding:1.25rem;
    }
    .ph-form-title { margin:0 0 1.1rem; font-size:1rem; font-weight:800; color:#1e293b; }
    .ph-form-grid { display:grid; grid-template-columns:1fr 1fr; gap:.8rem; }
    @media (max-width:580px) { .ph-form-grid { grid-template-columns:1fr; } }
    .ph-field { display:flex; flex-direction:column; gap:.3rem; }
    .ph-field--full { grid-column:1/-1; }
    .ph-field label { font-size:.8rem; font-weight:700; color:#374151; }
    .ph-input {
      padding:.65rem .9rem; border:1.5px solid #e2e8f0; border-radius:.75rem;
      font-size:.9rem; width:100%; background:#fff;
      transition:border-color .15s, box-shadow .15s;
      color:#1e293b;
    }
    .ph-input:focus { outline:none; border-color:#2563eb; box-shadow:0 0 0 3px rgba(37,99,235,.1); }
    .ph-input--disabled { background:#f8fafc; cursor:not-allowed; color:#9ca3af; }
    .ph-input select { appearance:none; }
    .ph-err { color:#dc2626; font-size:.76rem; }
    .ph-hint { color:#94a3b8; font-size:.76rem; }
    .ph-hint--block { display:block; margin-bottom:.8rem; }
    .ph-opt { color:#94a3b8; font-weight:400; }
    .ph-req { color:#dc2626; }
    .ph-pinrow { display:flex; gap:.5rem; }
    .ph-pinrow .ph-input { flex:1; }
    .ph-lookup-btn { white-space:nowrap; }
    .ph-form-actions { margin-top:1.35rem; display:flex; justify-content:flex-end; }

    /* ── Notification toggles ── */
    .ph-notif { margin-top:1.25rem; padding-top:1rem; border-top:1px solid #f1f5f9; }
    .ph-notif h4 { font-size:.86rem; font-weight:800; margin:0 0 .7rem; color:#1e293b; }
    .ph-toggle-grid { display:grid; grid-template-columns:1fr 1fr; gap:.55rem; }
    @media (max-width:500px) { .ph-toggle-grid { grid-template-columns:1fr; } }
    .ph-toggle {
      display:flex; align-items:center; gap:.6rem;
      font-size:.84rem; font-weight:500; cursor:pointer; color:#374151;
      background:#f8fafc; border:1px solid #e2e8f0; border-radius:.625rem;
      padding:.5rem .75rem;
    }
    .ph-toggle:hover { background:#eff6ff; border-color:#bfdbfe; }
    .ph-toggle input[type=checkbox] { display:none; }
    .ph-toggle-track {
      width:36px; height:20px; border-radius:999px;
      background:#cbd5e1; position:relative; flex-shrink:0;
      transition:background .2s;
    }
    .ph-toggle-track::after {
      content:''; width:14px; height:14px; border-radius:50%;
      background:#fff; position:absolute; top:3px; left:3px;
      box-shadow:0 1px 4px rgba(0,0,0,.2);
      transition:transform .2s;
    }
    .ph-toggle input:checked + .ph-toggle-track { background:#2563eb; }
    .ph-toggle input:checked + .ph-toggle-track::after { transform:translateX(16px); }


    /* ── Shared ── */
    .mi { font-family:'Material Icons',sans-serif; font-style:normal; line-height:1; display:inline-block; }
    .mi-sm { font-size:15px; }
    .btn {
      display:inline-flex; align-items:center; gap:.35rem;
      border-radius:.75rem; padding:.6rem 1.25rem;
      font-weight:700; font-size:.86rem; cursor:pointer;
      border:1.5px solid transparent; transition:all .15s;
    }
    .btn:disabled { opacity:.5; cursor:not-allowed; }
    .btn-primary { background:linear-gradient(135deg,#2563eb,#1d4ed8); color:#fff; box-shadow:0 4px 12px rgba(37,99,235,.25); }
    .btn-primary:hover:not(:disabled) { background:linear-gradient(135deg,#1d4ed8,#1e40af); box-shadow:0 6px 18px rgba(37,99,235,.35); transform:translateY(-1px); }
    .btn-outline { background:#fff; color:#2563eb; border-color:#bfdbfe; }
    .btn-outline:hover:not(:disabled) { background:#eff6ff; }

    @media (max-width:640px) {
      .ph-hero-inner { flex-direction:column; }
      .ph-hero-comp { text-align:left; min-width:0; width:100%; }
    }
  `],
})
export class ProfileViewComponent implements OnInit {
  private authService = inject(AuthService);
  private notification = inject(NotificationService);
  private fb = inject(FormBuilder);

  user = signal<User | null>(null);
  loading = signal(true);
  error = signal('');
  activeTab = signal<ProfileTab>('overview');
  savingPersonal = signal(false);
  savingAddress = signal(false);
  savingPrefs = signal(false);
  lookingUpPin = signal(false);

  readonly tabs: { id: ProfileTab; label: string; icon: string }[] = [
    { id: 'overview',    label: 'Overview',   icon: 'dashboard' },
    { id: 'personal',    label: 'Personal',   icon: 'person' },
    { id: 'address',     label: 'Address',    icon: 'location_on' },
    { id: 'preferences', label: 'Preferences', icon: 'tune' },
  ];

  readonly notifToggles = [
    { key: 'notifPush',  label: 'Push notifications' },
    { key: 'notifEmail', label: 'Email notifications' },
    { key: 'notifSms',   label: 'SMS notifications' },
    { key: 'notifInApp', label: 'In-app alerts' },
  ];

  personalForm!: FormGroup;
  addressForm!: FormGroup;
  prefsForm!: FormGroup;

  initials = computed(() => {
    const name = this.user()?.name || '';
    const parts = name.trim().split(/\s+/).filter(Boolean);
    return parts.slice(0, 2).map(p => p[0]?.toUpperCase() || '').join('') || 'PP';
  });

  completionChecklist = computed(() => {
    const u = this.user();
    if (!u) return [];
    return [
      { label: 'Name',          done: !!u.name?.trim(),         tab: 'personal'     as ProfileTab },
      { label: 'Phone',         done: !!u.phone?.trim(),        tab: 'personal'     as ProfileTab },
      { label: 'Email',         done: !!u.email?.trim(),        tab: 'personal'     as ProfileTab },
      { label: 'Address',       done: !!u.addressLine1?.trim(), tab: 'address'      as ProfileTab },
      { label: 'City',          done: !!u.city?.trim(),         tab: 'address'      as ProfileTab },
      { label: 'Pincode',       done: !!u.pincode?.trim(),      tab: 'address'      as ProfileTab },
      { label: 'Language pref', done: !!u.languagePreference,   tab: 'preferences'  as ProfileTab },
    ];
  });

  completionPct = computed(() => {
    const list = this.completionChecklist();
    if (!list.length) return 0;
    const done = list.filter(i => i.done).length;
    return Math.round((done / list.length) * 100);
  });

  missingCount = computed(() => this.completionChecklist().filter(i => !i.done).length);

  ngOnInit() {
    this.initForms();
    this.load();
  }

  private initForms(): void {
    this.personalForm = this.fb.group({
      name:  ['', Validators.required],
      phone: ['', [Validators.required, Validators.pattern(/^[6-9]\d{9}$/)]],
      email: [{ value: '', disabled: true }],
    });
    this.addressForm = this.fb.group({
      addressLine1:       [''],
      addressLine2:       [''],
      pincode:            [''],
      city:               [''],
      state:              [''],
      countryOfResidence: [''],
    });
    this.prefsForm = this.fb.group({
      languagePreference: ['en'],
      timezone:           ['Asia/Kolkata'],
      currencyPreference: ['INR'],
      notifPush:  [false],
      notifEmail: [false],
      notifSms:   [false],
      notifInApp: [false],
    });
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.authService.getProfile().subscribe({
      next: (u) => {
        this.user.set(u);
        this.patchForms(u);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Could not load profile. Please check your connection and try again.');
      },
    });
  }

  private patchForms(u: User): void {
    this.personalForm.patchValue({
      name:  u.name  || '',
      phone: u.phone || '',
      email: u.email || '',
    });
    this.addressForm.patchValue({
      addressLine1:       u.addressLine1       || '',
      addressLine2:       u.addressLine2       || '',
      pincode:            u.pincode            || '',
      city:               u.city               || '',
      state:              u.state              || '',
      countryOfResidence: u.countryOfResidence || 'India',
    });
    const notifPrefs = (u.notificationPreferences as Record<string, boolean> | undefined) || {};
    this.prefsForm.patchValue({
      languagePreference: u.languagePreference || 'en',
      timezone:           u.timezone           || 'Asia/Kolkata',
      currencyPreference: u.currencyPreference || 'INR',
      notifPush:  !!notifPrefs['push'],
      notifEmail: !!notifPrefs['email'],
      notifSms:   !!notifPrefs['sms'],
      notifInApp: !!notifPrefs['in_app'],
    });
  }

  setTab(tab: ProfileTab): void {
    this.activeTab.set(tab);
  }

  savePersonal(): void {
    if (this.personalForm.invalid) { this.personalForm.markAllAsTouched(); return; }
    this.savingPersonal.set(true);
    const v = this.personalForm.getRawValue();
    this.authService.updateProfile({ name: v.name, phone: v.phone }).subscribe({
      next: (u) => { this.user.set(u); this.savingPersonal.set(false); this.notification.showSuccess('Personal info updated!'); },
      error: (err) => { this.savingPersonal.set(false); this.notification.showError(err?.error?.detail || 'Failed to save.'); },
    });
  }

  saveAddress(): void {
    this.savingAddress.set(true);
    const v = this.addressForm.getRawValue();
    this.authService.updateProfile({
      addressLine1:       v.addressLine1,
      addressLine2:       v.addressLine2,
      pincode:            v.pincode,
      city:               v.city,
      state:              v.state,
      countryOfResidence: v.countryOfResidence,
    }).subscribe({
      next: (u) => { this.user.set(u); this.savingAddress.set(false); this.notification.showSuccess('Address updated!'); },
      error: (err) => { this.savingAddress.set(false); this.notification.showError(err?.error?.detail || 'Failed to save.'); },
    });
  }

  savePrefs(): void {
    this.savingPrefs.set(true);
    const v = this.prefsForm.getRawValue();
    this.authService.updateProfile({
      languagePreference: v.languagePreference,
      timezone:           v.timezone,
      currencyPreference: v.currencyPreference,
      notificationPreferences: {
        push:   v.notifPush,
        email:  v.notifEmail,
        sms:    v.notifSms,
        in_app: v.notifInApp,
      },
    }).subscribe({
      next: (u) => { this.user.set(u); this.savingPrefs.set(false); this.notification.showSuccess('Preferences updated!'); },
      error: (err) => { this.savingPrefs.set(false); this.notification.showError(err?.error?.detail || 'Failed to save.'); },
    });
  }



  lookupPincode(): void {
    const pincode = this.addressForm.get('pincode')?.value?.trim();
    if (!pincode || pincode.length !== 6) {
      this.notification.showError('Enter a valid 6-digit pincode first.');
      return;
    }
    this.lookingUpPin.set(true);
    this.authService.lookupPincode(pincode).subscribe({
      next: (res) => {
        this.lookingUpPin.set(false);
        const addr = res?.addresses?.[0];
        if (addr) {
          this.addressForm.patchValue({
            city:               addr.city  || addr.district || '',
            state:              addr.state || '',
            countryOfResidence: 'India',
          });
          this.notification.showSuccess('Pincode found — city and state updated.');
        } else {
          this.notification.showInfo('No address found for this pincode.');
        }
      },
      error: () => { this.lookingUpPin.set(false); this.notification.showError('Pincode lookup failed.'); },
    });
  }
}
