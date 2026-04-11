/** Production: always use HTTPS for app and apiUrl. See docs/AUTH_STORAGE_SECURITY.md */
export const environment = {
  production: true,
  appName: 'PARKPE',
  appVersion: '1.0.0',
  apiUrl: 'https://api.parkpe.com',
  apiTimeout: 30000,
  useMockApi: false, // Use real backend in production
  logLevel: 'info' as 'debug' | 'info' | 'warn' | 'error',
  sendLogsToBackend: false,

  paymentGateways: {
    cashfree: {
      enabled: true,
      appId: 'YOUR_CASHFREE_PRODUCTION_APP_ID',
      scriptUrl: 'https://sdk.cashfree.com/js/v3/cashfree.js',
      environment: 'production',
      currency: 'INR',
      callbackUrl: 'https://parkpe.com/payment/callback/cashfree',
      returnUrl: 'https://parkpe.com/payment/callback/cashfree',
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
      expiryTime: 3600000,
      refreshThreshold: 300000
    },
    session: {
      timeout: 1800000,
      warningTime: 300000
    },
    rateLimit: {
      maxRequests: 100,
      windowMs: 900000
    }
  },

  /** ParkPe Connect app (secure vehicle communication) – full app URL */
  connectAppUrl: 'https://connect.parkpe.in',

  features: {
    parking: true,
    bbps: true,
    fastag: true,
    challan: true,
    connect: true,
    callingService: true,
    qrScanner: true,
    notifications: true,
    analytics: true,
    darkMode: true
  },

  bbps: {
    apiUrl: 'https://api.parkpe.com/bbps',
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
    apiKey: 'YOUR_PRODUCTION_GOOGLE_MAPS_API_KEY',
    libraries: ['places', 'geometry']
  },

  analytics: {
    googleAnalyticsId: 'G-XXXXXXXXXX',
    mixpanelToken: 'YOUR_MIXPANEL_TOKEN',
    enabled: true
  },

  notification: {
    firebase: {
      apiKey: 'YOUR_FIREBASE_API_KEY',
      authDomain: 'parkpe.firebaseapp.com',
      projectId: 'parkpe',
      storageBucket: 'parkpe.appspot.com',
      messagingSenderId: 'YOUR_SENDER_ID',
      appId: 'YOUR_APP_ID'
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
