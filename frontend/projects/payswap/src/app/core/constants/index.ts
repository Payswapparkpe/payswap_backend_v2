import { InjectionToken } from '@angular/core';
import { ApiBackend } from '../api/api-backend.interface';

/**
 * Injection token for API Backend
 * Allows switching between MockApiService and RealApiService
 */
export const API_BACKEND_TOKEN = new InjectionToken<ApiBackend>('API_BACKEND');

/**
 * Application Constants
 */
export const APP_CONSTANTS = {
  APP_NAME: 'PAYSWAP',
  COPYRIGHT: '© 2024 PAYSWAP. All rights reserved.',
  VERSION: '1.0.0',
  SUPPORT_EMAIL: 'support@payswap.com',
  SUPPORT_PHONE: '+91-1800-123-4567',
};

/**
 * Route Constants
 */
export const ROUTES = {
  HOME: '/landing',
  LOGIN: '/auth/login',
  REGISTER: '/auth/register',
  FORGOT_PASSWORD: '/auth/forgot-password',
  DASHBOARD: '/dashboard',
  PARKING: '/parking',
  BBPS: '/bbps',
  FASTAG: '/fastag',
  CHALLAN: '/challan',
  PAYMENT: '/payment',
  PROFILE: '/profile',
  SETTINGS: '/settings',
};

/**
 * Storage Keys
 * Note: Avoid localStorage/sessionStorage in production
 * Use httpOnly cookies or in-memory storage
 */
export const STORAGE_KEYS = {
  THEME: 'payswap_theme',
  LANGUAGE: 'payswap_language',
};

/**
 * API Endpoints (relative to apiUrl)
 */
export const API_ENDPOINTS = {
  // Auth
  LOGIN: '/auth/login',
  REGISTER: '/auth/register',
  LOGOUT: '/auth/logout',
  PROFILE: '/auth/profile',
  FORGOT_PASSWORD: '/auth/forgot-password',

  // Payment
  GATEWAYS: '/payment/gateways',
  CREATE_ORDER: '/payment/create-order',
  VERIFY_PAYMENT: '/payment/verify',
  TRANSACTIONS: '/payment/transactions',

  // Parking
  PARKING_LOCATIONS: '/parking/locations',
  PARKING_BOOKINGS: '/parking/bookings',

  // BBPS
  BBPS_CATEGORIES: '/bbps/categories',
  BBPS_OPERATORS: '/bbps/operators',
  BBPS_FETCH_BILL: '/bbps/fetch-bill',
  BBPS_PAY: '/bbps/pay',

  // FASTag
  FASTAG_RECHARGE: '/fastag/recharge',

  // Challan
  CHALLAN_SEARCH: '/challan/search',
  CHALLAN_PAY: '/challan/pay',

  // Dashboard
  DASHBOARD_SUMMARY: '/dashboard/summary',
};
