export const environment = {
  production: false,
  appName: 'PARKPE',
  appVersion: '1.0.0',
  apiUrl: '/api',
  /** Partner API key for Engine; required for /api/connect, /api/bbps, /api/payment, /api/voucher. Set via env or build. Production: use FROM_ENV only. */
  apiKey: undefined as string | undefined,
  apiTimeout: 30000,
  useMockApi: false, // false = real backend at /api (proxy to localhost:8000)
  logLevel: 'debug' as 'debug' | 'info' | 'warn' | 'error',
  sendLogsToBackend: false,

  paymentGateways: {
    cashfree: {
      enabled: true,
      appId: 'YOUR_CASHFREE_APP_ID',
      scriptUrl: 'https://sdk.cashfree.com/js/v3/cashfree.js',
      environment: 'sandbox',
      currency: 'INR',
      callbackUrl: `${window.location.origin}/payment/callback/cashfree`,
      returnUrl: `${window.location.origin}/payment/callback/cashfree`,
      theme: {
        color: '#004aad',
        backgroundColor: '#ffffff'
      },
      timeout: 300000
    }
  },

  payment: {
    minAmount: 1,
    maxAmount: 100000,
    defaultGateway: 'cashfree' as 'razorpay' | 'cashfree',
    supportedMethods: ['card', 'netbanking', 'upi', 'wallet'],
    retryAttempts: 3,
    retryDelay: 2000,
    transactionTimeout: 300000,
    enableAutoRetry: true,
    webhook: {
      cashfree: '/webhooks/cashfree'
    }
  },

  security: {
    encryption: {
      algorithm: 'AES',
      keySize: 256
    },
    token: {
      expiryTime: 3600000, // 1 hour
      refreshThreshold: 300000 // 5 minutes
    },
    session: {
      timeout: 1800000, // 30 minutes
      warningTime: 300000 // 5 minutes
    },
    rateLimit: {
      maxRequests: 100,
      windowMs: 900000 // 15 minutes
    }
  },

  /** ParkPe Connect app (secure vehicle communication) – full app URL */
  connectAppUrl: 'https://connect.parkpe.in',

  features: {
    parking: false,
    bbps: true,
    fastag: true,
    challan: false,
    connect: true,
    callingService: true,
    qrScanner: true,
    notifications: true,
    analytics: false,
    darkMode: true
  },

  /** Mobikwik static CDN base URL for biller icons. Keep as single source of truth. */
  mobikwikIconBase: 'https://static.mobikwik.com/appdata/operator_icons',

  /** BBPS uses main apiUrl (e.g. /api) for all calls; this key is legacy/unused. Do not use for requests. */
  bbps: {
    // IMPORTANT: keep relative so LAN devices don't hit their own localhost
    apiUrl: '/api/bbps',
    timeout: 30000,
    categories: [
      'electricity',
      'water',
      'gas',
      'dth',
      'broadband',
      'mobile_postpaid',
      'landline',
      'insurance',
      'loan_repayment',
      'municipal_taxes'
    ]
  },

  googleMaps: {
    apiKey: 'YOUR_GOOGLE_MAPS_API_KEY',
    libraries: ['places', 'geometry']
  },

  analytics: {
    googleAnalyticsId: '',
    mixpanelToken: '',
    enabled: false
  },

  notification: {
    firebase: {
      apiKey: '',
      authDomain: '',
      projectId: '',
      storageBucket: '',
      messagingSenderId: '',
      appId: ''
    }
  },

  app: {
    defaultLanguage: 'en',
    supportedLanguages: [
      { code: 'en', label: 'English' },
      { code: 'hi', label: 'हिंदी' },
      { code: 'ta', label: 'தமிழ்' },
      { code: 'te', label: 'తెలుగు' },
      { code: 'mr', label: 'मराठी' },
      { code: 'bn', label: 'বাংলা' },
      { code: 'kn', label: 'ಕನ್ನಡ' },
      { code: 'ml', label: 'മലയാളം' },
      { code: 'gu', label: 'ગુજરાતી' },
      { code: 'pa', label: 'ਪੰਜਾਬੀ' }
    ],
    dateFormat: 'dd/MM/yyyy',
    timeFormat: 'HH:mm',
    currency: 'INR',
    currencySymbol: '₹'
  }
};
