import { Routes } from '@angular/router';

export const PARKING_ROUTES: Routes = [
  {
    path: '',
    redirectTo: 'list',
    pathMatch: 'full',
  },
  {
    path: 'list',
    loadComponent: () =>
      import('./parking-list/parking-list.component').then(
        (m) => m.ParkingListComponent
      ),
  },
  {
    path: 'slot/:locationId',
    loadComponent: () =>
      import('./parking-slot-select/parking-slot-select.component').then(
        (m) => m.ParkingSlotSelectComponent
      ),
  },
  {
    path: 'booking/:slotId',
    loadComponent: () =>
      import('./parking-booking/parking-booking.component').then(
        (m) => m.ParkingBookingComponent
      ),
  },
  {
    path: 'detail/:bookingId',
    loadComponent: () =>
      import('./parking-detail/parking-detail.component').then(
        (m) => m.ParkingDetailComponent
      ),
  },
];
