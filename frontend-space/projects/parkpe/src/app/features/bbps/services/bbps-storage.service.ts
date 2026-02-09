import { Injectable, signal, computed } from '@angular/core';

const FAVORITES_KEY = 'parkpe_bbps_favorites';
const SAVED_BILLS_KEY = 'parkpe_bbps_saved_bills';

export interface SavedBill {
  id: string;
  nickname: string;
  operatorId: string;
  operatorName: string;
  category: string;
  consumerId: string;
  lastAmount?: number;
  billId?: string;
  createdAt: string;
}

/** Stored favorite biller so we can show name and category on the category step without loading operators */
export interface FavoriteBiller {
  operatorId: string;
  operatorName: string;
  category: string;
}

@Injectable({ providedIn: 'root' })
export class BBPSStorageService {
  private favorites = signal<FavoriteBiller[]>(this.loadFavorites());
  private savedBills = signal<SavedBill[]>(this.loadSavedBills());

  /** For backward compatibility and star icon state: set of favorite operator IDs */
  favoriteOperatorIds = computed(() => this.favorites().map((f) => f.operatorId));
  /** Full list for displaying on category step (Favorite biller panel) */
  favoriteBillersList = this.favorites.asReadonly();
  savedBillsList = this.savedBills.asReadonly();

  isFavorite(operatorId: string): boolean {
    return this.favorites().some((f) => f.operatorId === operatorId);
  }

  toggleFavorite(operatorId: string, operatorName?: string, category?: string): void {
    const list = this.favorites();
    const existing = list.find((f) => f.operatorId === operatorId);
    const next = existing
      ? list.filter((f) => f.operatorId !== operatorId)
      : [
          ...list,
          {
            operatorId,
            operatorName: operatorName ?? 'Biller',
            category: category ?? '',
          },
        ];
    this.favorites.set(next);
    this.persistFavorites(next);
  }

  addSavedBill(bill: Omit<SavedBill, 'id' | 'createdAt'>): void {
    const newBill: SavedBill = {
      ...bill,
      id: `saved_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      createdAt: new Date().toISOString(),
    };
    const next = [newBill, ...this.savedBills()].slice(0, 50);
    this.savedBills.set(next);
    this.persistSavedBills(next);
  }

  updateSavedBillNickname(id: string, nickname: string): void {
    const next = this.savedBills().map((b) =>
      b.id === id ? { ...b, nickname: nickname.trim() || b.nickname } : b
    );
    this.savedBills.set(next);
    this.persistSavedBills(next);
  }

  removeSavedBill(id: string): void {
    const next = this.savedBills().filter((b) => b.id !== id);
    this.savedBills.set(next);
    this.persistSavedBills(next);
  }

  private loadFavorites(): FavoriteBiller[] {
    try {
      const raw = localStorage.getItem(FAVORITES_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      // Migrate old format (string[]) to FavoriteBiller[]
      return arr.map((item) =>
        typeof item === 'string'
          ? { operatorId: item, operatorName: 'Biller', category: '' }
          : {
              operatorId: item.operatorId ?? '',
              operatorName: item.operatorName ?? 'Biller',
              category: item.category ?? '',
            }
      ).filter((f) => f.operatorId);
    } catch {
      return [];
    }
  }

  private loadSavedBills(): SavedBill[] {
    try {
      const raw = localStorage.getItem(SAVED_BILLS_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  }

  private persistFavorites(list: FavoriteBiller[]): void {
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(list));
    } catch {}
  }

  private persistSavedBills(list: SavedBill[]): void {
    try {
      localStorage.setItem(SAVED_BILLS_KEY, JSON.stringify(list));
    } catch {}
  }
}
