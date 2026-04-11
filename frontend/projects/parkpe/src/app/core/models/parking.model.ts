// Parking Location
export interface ParkingLocation {
  id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  postalCode: string;
  slotsCount: number;
  availableSlots: number;
  rates: ParkingRate[];
  coordinates?: {
    latitude: number;
    longitude: number;
  };
  amenities?: string[];
  openingHours?: {
    open: string;
    close: string;
  };
  description?: string;
  images?: string[];
}

// Parking Rate
export interface ParkingRate {
  durationType: 'hourly' | 'daily' | 'weekly' | 'monthly';
  amount: number;
  currency: string;
  description?: string;
}

// Parking Slot
export interface ParkingSlot {
  id: string;
  locationId: string;
  code: string; // e.g., "A-101"
  available: boolean;
  vehicleType?: 'two_wheeler' | 'four_wheeler' | 'heavy_vehicle';
  rate: number;
  currency: string;
  features?: string[]; // e.g., "covered", "ev_charging"
}

// Booking Request
export interface BookingRequest {
  locationId: string;
  slotId: string;
  vehicleNumber: string;
  vehicleType: string;
  from: Date | string;
  to: Date | string;
  customerName: string;
  customerPhone: string;
  customerEmail: string;
}

// Booking
export interface Booking {
  id: string;
  locationId: string;
  locationName: string;
  slotId: string;
  slotCode: string;
  vehicleNumber: string;
  vehicleType: string;
  from: Date | string;
  to: Date | string;
  duration: number; // in minutes
  amount: number;
  currency: string;
  status: 'pending' | 'confirmed' | 'active' | 'completed' | 'cancelled';
  customer: {
    name: string;
    phone: string;
    email: string;
  };
  qrCode?: string;
  bookingReference: string;
  createdAt: Date | string;
  paymentId?: string;
}

// Parking State (for NgRx)
export interface ParkingState {
  locations: ParkingLocation[];
  selectedLocation: ParkingLocation | null;
  slots: ParkingSlot[];
  selectedSlot: ParkingSlot | null;
  booking: Booking | null;
  loading: boolean;
  error: string | null;
}
