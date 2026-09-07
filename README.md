MaishaWatch Backend API — Complete Setup & Operations Guide
📋 Table of Contents
Project Overview

System Requirements

Installation & Setup

Configuration

Database Setup

ML Model Setup

Data Import & Sync

Running the Application

Testing the API

API Endpoints Reference

Security Model

Email Configuration

Background Services

Troubleshooting

🏥 Project Overview
MaishaWatch is a comprehensive Predictive Maintenance and Hospital Equipment Operations Platform built with FastAPI. It provides real-time monitoring, predictive analytics, and maintenance management for medical equipment across healthcare facilities in Kenya.

Key Features
🔐 Secure Authentication with JWT and OTP verification

👥 Role-Based Access Control (7 user roles)

🏥 Equipment Management with CSV data sync

🧠 ML-Powered Predictions (Failure probability & RUL)

🚨 Alert Management with severity levels

🔧 Maintenance Work Orders

📧 Email Notifications with HTML templates

📊 Real-time Dashboard & Reports

🔍 Complete Audit Trail

💬 Operational Chat Assistant

Technology Stack
Framework: FastAPI 2.1.0

Database: SQLite (production: PostgreSQL/MySQL ready)

Authentication: JWT with OTP verification

ML Models: Scikit-learn (Random Forest)

Email: SMTP (Gmail/any SMTP)

Background Tasks: FastAPI BackgroundTasks + Threading

💻 System Requirements
Minimum Requirements
Python: 3.10 or higher

RAM: 4GB (8GB recommended)

Storage: 2GB free space

OS: Windows, Linux, or macOS

Python Dependencies
text
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.1.1
pandas==2.1.3
numpy==1.26.2
scikit-learn==1.3.2
joblib==1.3.2
email-validator==2.1.0
pydantic==2.5.0
pydantic-settings==2.1.0
httpx==0.25.1
🚀 Installation & Setup
Step 1: Clone Repository
bash
git clone https://github.com/yourusername/maishawatch-backend.git
cd maishawatch-backend
Step 2: Create Virtual Environment
Windows (PowerShell)
powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Linux/macOS
bash
python3 -m venv .venv
source .venv/bin/activate
Step 3: Install Dependencies
bash
pip install --upgrade pip
pip install -r requirements.txt
Step 4: Create Project Structure
powershell
# Windows
New-Item -ItemType Directory -Force -Path "app\core"
New-Item -ItemType Directory -Force -Path "app\api\routers"
New-Item -ItemType Directory -Force -Path "app\services"
New-Item -ItemType Directory -Force -Path "app\engines"
New-Item -ItemType Directory -Force -Path "app\ml"
New-Item -ItemType Directory -Force -Path "app\schemas"
New-Item -ItemType Directory -Force -Path "scripts"
New-Item -ItemType Directory -Force -Path "storage"
New-Item -ItemType Directory -Force -Path "data"
New-Item -ItemType Directory -Force -Path "models"
New-Item -ItemType Directory -Force -Path "logs"
Step 5: Create Required Files
Ensure the following files exist in your project:

text
maishawatch-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── security.py
│   │   ├── audit.py
│   │   └── paths.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── equipment.py
│   │       ├── facilities.py
│   │       ├── maintenance.py
│   │       ├── alerts.py
│   │       ├── notifications.py
│   │       ├── reports.py
│   │       ├── dashboard.py
│   │       ├── predictions.py
│   │       ├── audit.py
│   │       └── chat.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_service.py
│   │   ├── email_service.py
│   │   ├── notification_service.py
│   │   └── telemetry_service.py
│   ├── engines/
│   │   ├── __init__.py
│   │   └── alert_engine.py
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── predictor.py
│   │   ├── feature_builder.py
│   │   ├── risk_config.py
│   │   ├── recommendation_engine.py
│   │   └── schemas.py
│   └── schemas/
│       └── __init__.py
├── scripts/
│   ├── migrate_db.py
│   ├── seed_data.py
│   ├── import_data.py
│   └── sync_all_equipment.py
├── data/              # CSV data files
├── models/            # ML model files (.pkl)
├── storage/           # SQLite database
├── logs/              # Application logs
├── .env               # Environment variables
├── .env.example       # Example environment variables
├── requirements.txt
├── run.py
└── README.md
⚙️ Configuration
Step 1: Create .env File
Copy .env.example to .env and update values:

bash
cp .env.example .env
Step 2: Configure Environment Variables
env
# ============================
# Database
# ============================
DB_FILE=storage/maishawatch.db

# ============================
# JWT Authentication
# ============================
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# ============================
# CORS
# ============================
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# ============================
# SMTP Email Configuration
# ============================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_USE_TLS=true

# ============================
# Default Admin User
# ============================
DEFAULT_ADMIN_EMAIL=admin@maishawatch.com
DEFAULT_ADMIN_PASSWORD=Admin@123

# ============================
# Frontend URL
# ============================
SITE_URL=http://localhost:5173

# ============================
# ML/Risk Thresholds
# ============================
FAILURE_WARNING_THRESHOLD=0.30
FAILURE_HIGH_THRESHOLD=0.60
FAILURE_CRITICAL_THRESHOLD=0.80
RUL_WARNING_HOURS=168
RUL_MEDIUM_HOURS=72
RUL_HIGH_HOURS=24
RUL_CRITICAL_HOURS=8

# ============================
# Telemetry Simulation
# ============================
TELEMETRY_INTERVAL_SECONDS=60
TELEMETRY_ANOMALY_PROBABILITY=0.05
INITIAL_TELEMETRY_COUNT=100

# ============================
# Background Services
# ============================
EVALUATION_INTERVAL_HOURS=1
NOTIFICATION_RETRY_INTERVAL_MINUTES=5
NOTIFICATION_MAX_RETRIES=3
🗄️ Database Setup
Step 1: Run Database Migration
powershell
python scripts/migrate_db.py
This creates all required tables:

users - User accounts and roles

hospitals - Facility information

equipment_registry - Equipment master data

alerts - Alert records

maintenance_work_orders - Maintenance tasks

notification_queue - Notification history

audit_logs - System audit trail

otp_store - OTP verification

sensor_telemetry - Real-time sensor data

Step 2: Seed Initial Data
powershell
python scripts/seed_data.py
This creates:

Default admin user: admin@maishawatch.com / Admin@123

Sample facilities

Step 3: Verify Database
powershell
sqlite3 storage/maishawatch.db ".tables"
🧠 ML Model Setup
Step 1: Prepare Training Data
Place your dataset in data/ folder:

text
data/predictive_maintenance_dataset.csv
Step 2: Train Models (If not provided)
python
# scripts/train_models.py
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
import joblib

def train_models():
    # Load your training data
    df = pd.read_csv('data/predictive_maintenance_dataset.csv')
    
    # Train failure prediction models
    for horizon in [24, 72, 168]:
        # Training logic here
        model = RandomForestClassifier()
        # ... train ...
        joblib.dump(model, f'models/failure_model_{horizon}h.pkl')
    
    # Train RUL model
    rul_model = RandomForestRegressor()
    # ... train ...
    joblib.dump(rul_model, 'models/rul_model.pkl')
Step 3: Verify Models
Ensure these files exist in models/:

text
models/
├── failure_model_24h.pkl
├── failure_model_72h.pkl
├── failure_model_168h.pkl
├── rul_model.pkl
└── rul_features.pkl
📊 Data Import & Sync
Step 1: Prepare CSV Data
Place your CSV files in data/ folder:

text
data/
├── equipment_master.csv       # Equipment master data
├── sensor_telemetry.csv       # Sensor telemetry data
├── maintenance_history.csv    # Maintenance history
├── failure_events.csv         # Failure events
└── usage_reporting_log.csv    # Usage logs
Step 2: Import Data
powershell
python scripts/import_data.py
Step 3: Sync All Equipment
powershell
python scripts/sync_all_equipment.py
This syncs equipment to CSV and generates telemetry for equipment without data.

🚀 Running the Application
Method 1: Using run.py (Recommended)
powershell
python run.py
Method 2: Using uvicorn directly
powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Method 3: Production with gunicorn
bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
Verify Server is Running
bash
curl http://localhost:8000/health
Expected response:

json
{
  "status": "ok",
  "service": "maishawatch-api",
  "version": "2.1.0"
}
🧪 Testing the API
Step 1: Access Swagger UI
Open browser: http://127.0.0.1:8000/docs

Step 2: Test Authentication Flow
A. Login (First Time)
bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@maishawatch.com","password":"Admin@123"}'
Response:

json
{
  "requires_otp": true,
  "is_first_time": true,
  "message": "OTP sent to your email",
  "email": "admin@maishawatch.com",
  "otp_for_debug": "123456"
}
B. Get OTP from Database (Debug)
bash
sqlite3 storage/maishawatch.db "SELECT otp FROM otp_store WHERE email='admin@maishawatch.com' ORDER BY created_at DESC LIMIT 1;"
C. Verify OTP
bash
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@maishawatch.com","otp":"123456"}'
D. Change Temporary Password
bash
curl -X POST http://localhost:8000/auth/change-temp-password \
  -H "Content-Type: application/json" \
  -d '{
    "email":"admin@maishawatch.com",
    "temp_password":"Admin@123",
    "new_password":"YourNewPassword123!",
    "confirm_password":"YourNewPassword123!"
  }'
E. Login with New Password
bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@maishawatch.com","password":"YourNewPassword123!"}'
Step 3: Get Access Token
bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=admin@maishawatch.com&password=YourNewPassword123!"
Step 4: Test Protected Endpoint
bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
Step 5: Create a Test Hospital
bash
curl -X POST http://localhost:8000/facilities \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "facility_id": "HOSP-TEST-001",
    "facility_name": "Maisha Watch Test Hospital",
    "county": "Nairobi",
    "keph_level": "Level 5",
    "status": "ACTIVE"
  }'
Step 6: Create Equipment
bash
curl -X POST http://localhost:8000/equipment \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "equipment_id": "EQ-TEST-001",
    "facility_id": "HOSP-TEST-001",
    "equipment_type": "MRI Machine",
    "manufacturer": "Siemens",
    "model": "MAGNETOM Vida 3T",
    "serial_number": "SN-001",
    "installation_date": "2024-01-15T10:00:00",
    "simulate_telemetry": true,
    "telemetry_interval_seconds": 60
  }'
Step 7: Get ML Predictions
bash
curl -X POST http://localhost:8000/predict/failure/all \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"equipment_id": "EQ-TEST-001"}'
📚 API Endpoints Reference
Authentication (/auth)
Method	Endpoint	Description
POST	/auth/login	Login with email/password, returns OTP
POST	/auth/verify-otp	Verify OTP, returns access token
POST	/auth/change-temp-password	Change temporary password
POST	/auth/forgot-password	Request password reset OTP
POST	/auth/reset-password	Reset password with OTP
POST	/auth/change-password	Change password (authenticated)
GET	/auth/me	Get current user info
POST	/auth/logout	Logout
POST	/auth/token	OAuth2 token endpoint for Swagger
Users (/users)
Method	Endpoint	Description
GET	/users	List all users (filtered by scope)
POST	/users	Create new user with welcome email
PATCH	/users/{user_id}	Update user details
Facilities (/facilities)
Method	Endpoint	Description
GET	/facilities	List all facilities with equipment counts
POST	/facilities	Register new hospital
Equipment (/equipment)
Method	Endpoint	Description
GET	/equipment	List all equipment with filters
POST	/equipment	Register new equipment
GET	/equipment/{id}	Get equipment details
PUT	/equipment/{id}	Full equipment update
PATCH	/equipment/{id}	Partial equipment update
PATCH	/equipment/{id}/status	Update equipment status
DELETE	/equipment/{id}	Delete equipment
POST	/equipment/sync-all	Sync all equipment to CSV
POST	/equipment/{id}/generate-telemetry	Generate telemetry data
GET	/equipment/{id}/failure-prediction	Get failure prediction
GET	/equipment/{id}/rul	Get Remaining Useful Life
POST	/equipment/evaluate	Evaluate equipment
GET	/equipment/stats/summary	Equipment statistics
GET	/equipment/{id}/telemetry	Get telemetry data
GET	/equipment/{id}/alerts	Get equipment alerts
Alerts (/alerts)
Method	Endpoint	Description
GET	/alerts	List alerts with filters
POST	/alerts	Create manual alert
GET	/alerts/stats	Alert statistics
GET	/alerts/{id}	Get single alert
PUT	/alerts/{id}	Full alert update
PATCH	/alerts/{id}	Partial alert update
PATCH	/alerts/{id}/acknowledge	Acknowledge alert
PATCH	/alerts/{id}/resolve	Resolve alert
PATCH	/alerts/{id}/close	Close resolved alert
POST	/alerts/bulk	Bulk actions
DELETE	/alerts/{id}	Delete manual alert
DELETE	/alerts/bulk	Bulk delete alerts
GET	/alerts/equipment/{id}	Get alerts for equipment
GET	/alerts/facility/{id}	Get alerts for facility
ML Predictions (/predict)
Method	Endpoint	Description
POST	/predict/failure/24h	Failure probability (24h)
POST	/predict/failure/72h	Failure probability (72h)
POST	/predict/failure/168h	Failure probability (168h)
POST	/predict/failure/all	All horizons combined
POST	/predict/rul	Remaining Useful Life
POST	/predict/failure/batch	Batch failure predictions
POST	/predict/rul/batch	Batch RUL predictions
GET	/predict/config	Risk configuration
GET	/predict/history/{id}	Prediction history
GET	/predict/health	ML service health
Notifications (/notifications)
Method	Endpoint	Description
GET	/notifications	Get user notifications
GET	/notifications/unread-count	Unread count
GET	/notifications/queue	Notification queue (admin)
PATCH	/notifications/{id}/read	Mark as read
PATCH	/notifications/read-all	Mark all as read
POST	/notifications/send	Send manual notification
DELETE	/notifications/{id}	Delete notification
DELETE	/notifications/clear-all	Clear all notifications
GET	/notifications/stats	Notification statistics
Reports (/reports)
Method	Endpoint	Description
GET	/reports/summary	Full system summary
GET	/reports/equipment	Equipment report
GET	/reports/alerts	Alerts report
GET	/reports/maintenance	Maintenance report
Dashboard (/dashboard)
Method	Endpoint	Description
GET	/dashboard/summary	Dashboard summary
GET	/dashboard/equipment-status	Equipment status
GET	/dashboard/alerts-timeline	Alerts timeline
🔒 Security Model
Role-Based Access Control (RBAC)
Role	Permissions
system_administrator	Full system access, user management, national scope
national_administrator	National-level oversight, hospital registration
national_executive	National reports and monitoring
facility_manager	Facility-level equipment and user management
biomedical_engineer	Equipment technical management, maintenance
maintenance_technician	Work orders, equipment maintenance
clinician	Equipment availability, clinical monitoring
Security Features
✅ Password hashing (bcrypt)

✅ JWT token authentication

✅ OTP verification for all logins

✅ Role-based access control

✅ Audit logging for all actions

✅ CORS configuration

✅ Environment variables for sensitive data

✅ Facility scoping (users can only access their facility)

Scope Enforcement
Every protected endpoint derives identity and scope from the JWT. Facility-scoped users cannot retrieve another facility's equipment, alerts, maintenance history or work orders by changing an ID in the URL. The backend remains the enforcement point.

📧 Email Configuration
SMTP Setup
Gmail (Recommended)
Enable 2-Factor Authentication on your Google Account

Go to: https://myaccount.google.com/apppasswords

Generate an App Password for "Mail" and "Windows Computer"

Use the generated password in .env

Other SMTP Providers
Configure these variables in .env:

env
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USERNAME=your-email@provider.com
SMTP_PASSWORD=your-password
SMTP_FROM=your-email@provider.com
SMTP_USE_TLS=true
Email Templates
Welcome Email: Sent to new users with temporary password and login link

OTP Email: Sent during login and password reset

Equipment Registration: Role-specific notifications for new equipment

Alert Notifications: Severity-based alerts to relevant roles

Status Changes: Equipment status updates

🔄 Background Services
1. Telemetry Simulation
Purpose: Generate realistic sensor data for equipment

Frequency: Configurable interval (default 60 seconds)

Equipment Types: 15+ medical equipment types with realistic parameters

Anomaly Rate: 2-8% anomaly probability

2. Periodic Equipment Evaluation
Purpose: Auto-evaluate all equipment for failure risk

Frequency: Every hour

Actions: Check risk scores, create/update alerts

3. Notification Processing
Queue: SQLite-based notification queue

Delivery: SMTP email (non-blocking)

Retry: Failed notifications remain in queue

🔧 Troubleshooting
Common Issues & Solutions
1. ModuleNotFoundError
bash
# Solution: Install missing dependencies
pip install -r requirements.txt
2. Database Error: "no such table"
bash
# Solution: Run migrations
python scripts/migrate_db.py
3. SMTP Authentication Error
bash
# Solution: Use App Password for Gmail
# 1. Enable 2FA
# 2. Generate App Password at myaccount.google.com/apppasswords
# 3. Update .env with the new password
4. CORS Error
bash
# Solution: Update .env CORS_ORIGINS
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://yourdomain.com
5. ML Prediction Errors
bash
# Solution: Check model files
ls models/
# Should contain: failure_model_24h.pkl, failure_model_72h.pkl, 
# failure_model_168h.pkl, rul_model.pkl, rul_features.pkl
6. Port Already in Use
bash
# Windows: Find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8000
kill -9 <PID>
Debug Mode
bash
# Run with debug logging
python run.py
Logs Location
text
logs/
├── app.log         # Application logs
├── error.log       # Error logs
└── access.log      # Access logs
📝 Quick Start Commands Summary
powershell
# 1. Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Database
python scripts/migrate_db.py
python scripts/seed_data.py

# 3. Data Import
python scripts/import_data.py
python scripts/sync_all_equipment.py

# 4. Run Server
python run.py

# 5. Test
# Open http://127.0.0.1:8000/docs
🎯 API Status & Health
Health Check
bash
curl http://localhost:8000/health
API Documentation
Swagger UI: http://localhost:8000/docs

ReDoc: http://localhost:8000/redoc

OpenAPI JSON: http://localhost:8000/openapi.json

📖 Additional Resources
FastAPI Documentation

SQLite Documentation

Scikit-learn Documentation

JWT Documentation

🔐 Security Best Practices
Production Deployment:

Change all default passwords

Use strong JWT_SECRET_KEY

Enable HTTPS

Use PostgreSQL/MySQL instead of SQLite

Set DEBUG=false

Email:

Use OAuth2 or App Passwords

Never store plain text passwords

Use TLS/SSL for SMTP

Database:

Regular backups

Use environment-specific configurations

Never commit database files

API:

Implement rate limiting

Use CORS properly

Validate all inputs

Sanitize outputs

📄 License
This project is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

🤝 Support
For issues, questions, or support:

Email: watchmaisha@gmail.com

GitHub Issues: Create an issue

🏁 Conclusion
Your MaishaWatch Backend is now fully set up and running! The system provides:

✅ Complete authentication with OTP and RBAC

✅ Equipment management with CSV sync

✅ ML-powered predictions and alerts

✅ Email notifications

✅ Real-time monitoring

✅ Complete audit trail

Ready for frontend integration! 🚀