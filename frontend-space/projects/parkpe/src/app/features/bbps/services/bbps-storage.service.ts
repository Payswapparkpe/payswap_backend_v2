import { Injectable, signal, computed, inject } from '@angular/core';
import { tap, catchError, of } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';

export interface SavedBill {
  id: string;
  nickname: string;
  operatorId: string;
  operatorName: string;
  category: string;
  mobikwikOpId?: string;
  consumerId: string;
  lastAmount?: number;
  billId?: string;
  createdAt: string;
}

/** Stored favorite biller so we show name and category on the category step (from DB, sync across devices). */
export interface FavoriteBiller {
  operatorId: string;
  operatorName: string;
  category: string;
  mobikwikOpId?: string;
}

@Injectable({ providedIn: 'root' })
export class BBPSStorageService {
  private api = inject(API_BACKEND_TOKEN);

  private favorites = signal<FavoriteBiller[]>([]);
  private savedBills = signal<SavedBill[]>([]);

  /** For backward compatibility and star icon state: set of favorite operator IDs */
  favoriteOperatorIds = computed(() => this.favorites().map((f) => f.operatorId));
  /** Full list for displaying on category step (Favorite biller panel) */
  favoriteBillersList = this.favorites.asReadonly();
  savedBillsList = this.savedBills.asReadonly();

  isFavorite(operatorId: string): boolean {
    return this.favorites().some((f) => f.operatorId === operatorId);
  }

  /** Load favorites from backend (call when BBPS screen loads and user is authenticated). */
  refreshFavorites(): void {
    this.api.getBbpsFavorites().pipe(
      tap((list) => this.favorites.set(list ?? [])),
      catchError(() => {
        this.favorites.set([]);
        return of([]);
      }),
    ).subscribe();
  }

  /** Load saved bills from backend (call when BBPS screen loads and user is authenticated). */
  refreshSavedBills(): void {
    this.api.getBbpsSavedBills().pipe(
      tap((list) => this.savedBills.set(list ?? [])),
      catchError(() => {
        this.savedBills.set([]);
        return of([]);
      }),
    ).subscribe();
  }

  toggleFavorite(operatorId: string, operatorName?: string, category?: string, mobikwikOpId?: string): void {
    const existing = this.favorites().find((f) => f.operatorId === operatorId);
    if (existing) {
      this.api.removeBbpsFavorite(operatorId).pipe(
        tap(() => this.favorites.set(this.favorites().filter((f) => f.operatorId !== operatorId))),
        catchError(() => of(undefined)),
      ).subscribe();
    } else {
      this.api.addBbpsFavorite({
        operatorId,
        operatorName: operatorName ?? 'Biller',
        category: category ?? '',
        mobikwikOpId,
      }).pipe(
        tap((one) => this.favorites.set([one, ...this.favorites()])),
        catchError(() => of(undefined)),
      ).subscribe();
    }
  }

  addSavedBill(bill: Omit<SavedBill, 'id' | 'createdAt'>): void {
    this.api.addBbpsSavedBill({
      nickname: bill.nickname ?? '',
      operatorId: bill.operatorId,
      operatorName: bill.operatorName,
      category: bill.category ?? '',
      mobikwikOpId: bill.mobikwikOpId,
      consumerId: bill.consumerId,
      lastAmount: bill.lastAmount,
      billId: bill.billId,
    }).pipe(
      tap((created) => this.savedBills.set([created, ...this.savedBills()])),
      catchError(() => of(undefined)),
    ).subscribe();
  }

  updateSavedBillNickname(id: string, nickname: string): void {
    this.api.updateBbpsSavedBill(id, { nickname: nickname.trim() || '' }).pipe(
      tap((updated) => {
        this.savedBills.set(this.savedBills().map((b) => (b.id === id ? updated : b)));
      }),
      catchError(() => of(undefined)),
    ).subscribe();
  }

  removeSavedBill(id: string): void {
    this.api.removeBbpsSavedBill(id).pipe(
      tap(() => this.savedBills.set(this.savedBills().filter((b) => b.id !== id))),
      catchError(() => of(undefined)),
    ).subscribe();
  }
}
