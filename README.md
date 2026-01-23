# Payswap – Backend V2

**Payswap** is a fintech technology platform providing **digital payment infrastructure, prepaid solutions, and automated collections** for businesses, government bodies, and service providers.  
The backend is designed to be **secure, scalable, compliant, and API-first**, aligned with India's regulated fintech ecosystem.

---

## 🧱 Core Technology Stack

### Language & Framework
- Python **3.12+** (latest stable)
- **Django 6.x**
- **Django REST Framework**
- ASGI-first architecture
- Async-ready views, middleware, and background jobs

### Core Components
- Redis (cache, rate limits, queues)
- Celery (async task processing)
- PostgreSQL 16+
- Cryptography-secured services
- End-to-End Encryption & Signature Verification
- Content Security Policy (CSP)

---

## 🚀 Getting Started

### Prerequisites

Before setting up Payswap, ensure you have the following installed:

- **Python 3.12+**
- **PostgreSQL 16+**
- **Redis 7+**
- **pip** (Python package manager)
- **virtualenv** (recommended for environment isolation)

### Installation

#### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd payswap
```

#### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

#### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 4: Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

**Required Environment Variables:**

```env
# Application Configuration
APP_NAME=Payswap
APP_ENV=development
DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production
ALLOWED_HOSTS=127.0.0.1,localhost

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/payswap_db

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TIMEZONE=Asia/Kolkata

# Security Keys (REQUIRED - Generate strong random values in production)
JWT_SIGNING_KEY=your-jwt-signing-key-change-in-production
ENCRYPTION_KEY=your-encryption-key-change-in-production
SIGNING_SECRET=your-signing-secret-change-in-production
```

#### Step 5: Database Setup

```bash
# Create PostgreSQL database
createdb payswap_db

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

#### Step 6: Redis Setup

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
```

**Docker:**
```bash
docker run -d -p 6379:6379 redis:latest
```

**Verify Redis:**
```bash
redis-cli ping
# Expected output: PONG
```

#### Step 7: Run Configuration Tests

```bash
python tests/test_configuration.py
```

#### Step 8: Start Development Server

```bash
python manage.py runserver
```

Server will be available at `http://127.0.0.1:8000/`

#### Step 9: Start Celery Worker (Separate Terminal)

```bash
# Activate virtual environment
source .venv/bin/activate

# Option 1: Use the provided script (recommended - auto-detects platform)
./run_celery.sh

# Option 2: Manual command for macOS (if you encounter SIGSEGV errors)
celery -A core worker --loglevel=info --pool=solo

# Option 3: Manual command for Linux (default prefork)
celery -A core worker --loglevel=info --pool=prefork --concurrency=8

# Start Celery Beat (for scheduled tasks)
celery -A core beat --loglevel=info
```

**⚠️ macOS Users:** If you see `SIGSEGV` (segmentation fault) errors, use `--pool=solo` instead of the default `prefork` pool. See [docs/CELERY_TROUBLESHOOTING.md](docs/CELERY_TROUBLESHOOTING.md) for details.

### Access Points

- **Web Interface:** http://127.0.0.1:8000/
- **API Endpoints:** http://127.0.0.1:8000/api/v1/

---

## 🔐 Authentication & Authorization

### Authentication Methods
- JWT Authentication (Access & Refresh tokens)
- Token rotation & expiry enforcement
- API Key authentication for partner integrations
- OAuth2 ready

### Authorization Roles

#### Payswap Platform
- Admin
- Employee
- Super Distributor
- Distributor
- Retailer
- API Partner

#### Parkpe Platform
- Customer
- Vendor

### Security Features
- Role-Based Access Control (RBAC)
- Permission-based API access
- Object-level permissions
- Granular security-first approach

---

## 🛡️ Security Architecture

### Application Security
- HTTPS-only enforcement (HSTS enabled)
- Secure headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- CSRF & CORS protection
- Payload validation
- Clickjacking & MIME sniffing protection

### Cryptography & Data Protection
- AES-256 encryption for sensitive data at rest
- RSA/ECC key exchange
- Encrypted fields (bank details, identity references, tokens)
- Per-tenant encryption keys
- Key rotation support
- HSM/Vault compatible key storage

### API & Transport Security
- Request signing for financial APIs
- Timestamp & nonce validation (replay attack prevention)
- HMAC/RSA webhook signature verification
- IP allowlisting for critical endpoints
- Optional mTLS for bank integrations

### Identity Hardening
- Device fingerprinting
- Concurrent session limits
- Forced logout on credential changes
- Step-up authentication for high-risk actions
- Maker-Checker (dual approval) support

---

## 🧠 Fraud & Risk Controls

- Velocity & frequency checks
- Amount threshold monitoring
- Geo-location anomaly detection
- Device & IP reputation scoring
- Rule-based risk engine
- Auto-freeze & manual review workflows

---

## 🗄️ Database & Storage

### Primary Database
- PostgreSQL **16+**
- UUID primary keys
- ACID-compliant transactions
- Read replicas support
- Connection pooling

### Caching & Queues
- Redis (latest)
  - Session storage
  - OTP handling
  - Rate limiting
  - Caching layer

### File Storage
- S3-compatible object storage
- Encrypted document uploads (KYC, agreements)
- Signed URLs
- Virus scan integration

---

## ⚙️ Core Backend Modules

### User & Identity Management
- User onboarding & authentication
- Role & permission management
- KYC lifecycle handling
- Account management
- Full audit trail

### Wallet & Ledger System
- User/merchant wallets
- Double-entry ledger accounting
- Immutable transaction records
- Balance reconciliation
- Decimal-safe calculations

### Payments & Transactions
- Payment initiation & tracking
- Idempotent APIs
- Status polling & callbacks
- Retry & rollback handling
- Comprehensive failure mapping

### Prepaid & Stored Value
- Card & wallet mapping
- Balance synchronization
- Transaction management
- Lifecycle management

### Payouts & Virtual Accounts
- Beneficiary management
- Single & bulk payouts
- Virtual account mapping
- Settlement & reconciliation

### Utility & BBPS Integrations
- Bill fetch & payment
- Status reconciliation
- Commission & fee calculation
- Provider failover support

---

## 🔄 Queue & Async Processing

### Queue System
- Celery with Redis/RabbitMQ
- Segregated queues:
  - payments
  - wallets
  - payouts
  - notifications
  - webhooks
  - reports

### Queue Guarantees
- Idempotent task execution
- Exactly-once processing for financial operations
- Exponential retry with backoff
- Dead Letter Queues (DLQ)
- Priority queues
- Circuit breakers & timeouts

---

## 📣 Notification System

### Channels
- SMS (OTP & transactional)
- Email (alerts, reports, statements)
- Push notifications
- Partner webhooks

### Features
- Centralized notification service
- Template-based with version control
- Multi-language support
- Channel fallback logic
- Rate limiting per user & provider
- Delivery status tracking
- Provider performance metrics

### Notification Types
- Transaction confirmations
- Wallet updates
- KYC status changes
- Payout notifications
- Security alerts
- Compliance notifications

---

## 📡 API Design Standards

- RESTful JSON APIs
- Versioned endpoints (`/api/v1/`)
- Idempotency keys for financial operations
- Consistent error structures
- Pagination & filtering
- OpenAPI/Swagger documentation

---

## 📊 Logging, Monitoring & Audits

### Logging
- Structured JSON logs
- Correlation IDs
- Request/response tracing
- Error stack traces

### Monitoring
- Latency & error metrics
- Health check endpoints
- Queue & worker monitoring

### Audits
- Immutable audit logs
- Ledger-linked records
- Admin action tracking
- Compliance-ready exports

---

## 🧪 Testing & Quality

- Pytest framework
- Unit, integration & API tests
- External provider mocks
---



## 📁 Project Structure

```
payswap/
├── api/                 # API application
├── core/                # Core settings
├── portal/              # Portal application
├── templates/           # Django templates
├── static/              # Static files
├── tests/               # Test suite
├── logs/                # Log Related Data
├── utils/               # Utility Functions
├── tasks/               # Celery Tasks
├── docs/                # Documentation
├── manage.py            # Django management
├── requirements.txt     # Dependencies
└── .env                 # Environment variables (git-ignored)
```

---

## 🐛 Troubleshooting

### Database Issues
```bash
python manage.py dbshell
python manage.py check --database default
```

### Redis Issues
```bash
redis-cli ping
redis-cli monitor
```

### Celery Issues
```bash
celery -A core inspect active
celery -A core worker --loglevel=debug
```

---

## 📞 Support

For technical support and inquiries:
- **Email:** support@payswap.in
- **Documentation:** [Coming Soon]
- **API Docs:** [Coming Soon]

---

## 📄 License

Copyright © 2025 Payswap. All rights reserved.

See [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

---

**Built with ❤️ by the Payswap Team**