/**
 * Indian vehicle types, brands and models for ParkPe Connect.
 * Used for Add/Edit vehicle form: Type → Brand → Model.
 * RC API will be used later to enrich details; this is for initial identification.
 */

export type VehicleTypeId = 'two_wheeler' | 'four_wheeler' | 'commercial';

export interface VehicleTypeOption {
  id: VehicleTypeId;
  label: string;
}

export const VEHICLE_TYPES: VehicleTypeOption[] = [
  { id: 'two_wheeler', label: 'Bike/Scooty' },
  { id: 'four_wheeler', label: 'Private Car' },
  { id: 'commercial', label: 'Commercial' },
];

/** Brand name → list of model names */
export type BrandModels = Record<string, string[]>;

/** Vehicle type → brands and their models. Commercial = auto / taxi / big vehicles. */
export const VEHICLE_BRANDS_AND_MODELS: Record<VehicleTypeId, BrandModels> = {
  two_wheeler: {
    'Hero': ['Splendor', 'Splendor Plus', 'Passion', 'HF Deluxe', 'Glamour', 'Xtreme', 'Xtec', 'Pleasure', 'Destini', 'Maestro', 'Electric'],
    'Honda': ['Activa', 'Activa 6G', 'Dio', 'Shine', 'Unicorn', 'CB Shine', 'CB Hornet', 'CB350', 'CB300R', 'Grazia', 'Navi'],
    'TVS': ['Apache', 'Apache RTR', 'Raider', 'Jupiter', 'Jupiter 125', 'NTorq', 'Sport', 'Star City', 'Radeon', 'iQube', 'Ronin'],
    'Bajaj': ['Pulsar', 'Pulsar NS', 'Pulsar RS', 'Platina', 'CT', 'Dominar', 'Avenger', 'Chetak', 'Discover'],
    'Royal Enfield': ['Classic 350', 'Hunter 350', 'Meteor 350', 'Himalayan', 'Scram 411', 'Bullet 350', 'Interceptor 650', 'Continental GT 650'],
    'Yamaha': ['R15', 'FZ', 'FZ-S', 'Fascino', 'Ray ZR', 'Aerox', 'MT-15', 'YZF-R15'],
    'Suzuki': ['Access', 'Avenis', 'Burgman', 'Gixxer', 'Gixxer SF', 'V-Strom SX'],
    'Ola Electric': ['S1', 'S1 Pro', 'S1 Air'],
    'Ather Energy': ['450X', '450S', '450 Apex'],
    'Hero Electric': ['Optima', 'NYX', 'Flash', 'Eddy', 'Atria'],
    'Revolt': ['RV400', 'RV300'],
    'Jawa': ['Jawa', 'Forty Two', 'Perak', '42 2.1'],
    'KTM': ['Duke', 'RC', 'Adventure'],
    'Vespa': ['Vespa', 'VXL', 'SXL', 'Zx', 'Elettrica'],
  },
  four_wheeler: {
    'Maruti Suzuki': ['Swift', 'Dzire', 'Baleno', 'Brezza', 'Ertiga', 'Fronx', 'Invicto', 'Jimny', 'Alto', 'Wagon R', 'Celerio', 'S-Presso', 'Eeco', 'Ciaz', 'Grand Vitara', 'XL6', 'Ignis'],
    'Hyundai': ['i20', 'i10', 'Grand i10', 'Creta', 'Venue', 'Exter', 'Verna', 'Tucson', 'Alcazar', 'Kona Electric', 'Ioniq 5'],
    'Tata': ['Nexon', 'Punch', 'Harrier', 'Safari', 'Tiago', 'Tigor', 'Altroz', 'Curvv', 'Sierra', 'Avinya'],
    'Mahindra': ['XUV700', 'XUV300', 'Scorpio N', 'Scorpio Classic', 'Thar', 'Bolero', 'XUV400', 'Marazzo', 'XUV3XO'],
    'Honda': ['City', 'Amaze', 'Elevate', 'Jazz', 'WR-V', 'CR-V'],
    'Kia': ['Seltos', 'Sonet', 'Carens', 'EV6', 'Carnival'],
    'Toyota': ['Innova Crysta', 'Innova Hycross', 'Fortuner', 'Urban Cruiser', 'Hycross', 'Glanza', 'Rumion'],
    'MG': ['Hector', 'Gloster', 'ZS EV', 'Comet'],
    'Skoda': ['Slavia', 'Kushaq', 'Kodiaq', 'Superb'],
    'Volkswagen': ['Virtus', 'Taigun', 'Tiguan', 'Polo', 'T-Roc'],
    'Renault': ['Duster', 'Kiger', 'Triber', 'Kwid', 'Koleos'],
    'Nissan': ['Magnite', 'Kicks', 'X-Trail'],
    'Citroën': ['C3', 'C3 Aircross', 'eC3', 'C5 Aircross'],
    'Jeep': ['Compass', 'Meridian', 'Wrangler', 'Grand Cherokee'],
  },
  commercial: {
    'Tata': ['Ace', 'Ace EV', 'Winger', 'Intra', 'Yodha', 'Ultra', 'Signa', 'Prima', 'LPK'],
    'Mahindra': ['Bolero Pickup', 'Jeeto', 'Supro', 'Alfa Plus', 'Bolero Maxi', 'Blazo', 'Furio', 'Alfa', 'Alfa Mini', 'Treo', 'Treo Zor', 'Treo Yaari'],
    'Ashok Leyland': ['Dost', 'Boss', 'Partner', 'Captain', 'E-Comet'],
    'Eicher': ['Pro 2049', 'Pro 3015', 'Pro 3031', 'Skyline', 'Partner'],
    'Maruti Suzuki': ['Super Carry', 'Eeco Cargo', 'Tour S'],
    'Bajaj': ['RE', 'RE Compact', 'Maxima', 'Maxima C', 'Compact RE'],
    'Piaggio': ['Ape', 'Ape Xtra', 'Ape E-City', 'Ape E-City Cargo', 'Ape City', 'Ape DX'],
    'Force': ['Traveller', 'Trax', 'Urbania', 'Gurkha'],
    'SML Isuzu': ['SML', 'SML Mini', 'SML Grande'],
    'BharatBenz': ['1217', '1214', '3128', '4828', '3528'],
    'TVS': ['King', 'King Plus', 'Mobility'],
    'Atul Auto': ['Gem', 'Gem Plus', 'Shakti', 'Super Shakti'],
    'Euler': ['HiLoad', 'HiLoad Cargo'],
  },
};

/** Get brands for a vehicle type */
export function getBrandsForType(typeId: VehicleTypeId): string[] {
  const brands = VEHICLE_BRANDS_AND_MODELS[typeId];
  if (!brands) return [];
  return Object.keys(brands).sort();
}

/** Get models for a vehicle type and brand */
export function getModelsForBrand(typeId: VehicleTypeId, brand: string): string[] {
  const brands = VEHICLE_BRANDS_AND_MODELS[typeId];
  if (!brands || !brand) return [];
  return (brands[brand] ?? []).slice();
}

/** Get display label for vehicle type id (includes legacy three_wheeler -> Commercial). */
export function getVehicleTypeLabel(typeId: string): string {
  if (typeId === 'three_wheeler') return 'Commercial';
  const t = VEHICLE_TYPES.find((x) => x.id === typeId);
  return t ? t.label : typeId || '';
}
