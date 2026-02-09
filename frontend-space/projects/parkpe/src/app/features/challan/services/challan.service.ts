import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BACKEND_TOKEN } from '../../../core/constants';
import { ChallanSearchRequest, Challan } from '../../../core/models/challan.model';

@Injectable({
  providedIn: 'root',
})
export class ChallanService {
  private api = inject(API_BACKEND_TOKEN);

  searchChallans(request: ChallanSearchRequest): Observable<Challan[]> {
    return this.api.searchChallans(request);
  }

  getChallan(id: string): Observable<Challan> {
    return this.api.getChallan(id);
  }
}
