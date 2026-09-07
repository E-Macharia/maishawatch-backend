# MaishaWatch Backend API — Complete Setup & Operations Guide

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [System Requirements](#system-requirements)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Database Setup](#database-setup)
6. [Running the Application](#running-the-application)
7. [Testing the API](#testing-the-api)
8. [API Endpoints](#api-endpoints)
9. [Security Model](#security-model)
10. [Email Configuration](#email-configuration)
11. [Troubleshooting](#troubleshooting)

---

## 🏥 Project Overview

**MaishaWatch** is a comprehensive **Predictive Maintenance and Hospital Equipment Operations Platform** built with FastAPI. It provides real-time monitoring, predictive analytics, and maintenance management for medical equipment across healthcare facilities in Kenya.

### Key Features
- 🔐 **Secure Authentication** with JWT and OTP verification
- 👥 **Role-Based Access Control** (7 user roles)
- 🏥 **Equipment Management** with CSV data sync
- 🧠 **ML-Powered Predictions** (Failure probability & RUL)
- 🚨 **Alert Management** with severity levels
- 🔧 **Maintenance Work Orders**
- 📧 **Email Notifications** with HTML templates
- 📊 **Real-time Dashboard & Reports**
- 🔍 **Complete Audit Trail**
- 💬 **Operational Chat Assistant**

### Technology Stack
- **Framework**: FastAPI 2.1.0
- **Database**: SQLite (production: PostgreSQL/MySQL ready)
- **Authentication**: JWT with OTP verification
- **ML Models**: Scikit-learn (Random Forest)
- **Email**: SMTP (Gmail/any SMTP)
- **Background Tasks**: FastAPI BackgroundTasks + Threading

---

## 💻 System Requirements

### Minimum Requirements
- **Python**: 3.10 or higher
- **RAM**: 4GB (8GB recommended)
- **Storage**: 2GB free space
- **OS**: Windows, Linux, or macOS

---

## 🚀 Installation & Setup

### Step 1: Clone Repository
```bash
git clone https://github.com/E-Macharia/maishawatch-backend.git
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
Step 4: Configure Environment
bash
cp .env.example .env
# Edit .env with your configuration
⚙️ Configuration
Create .env file with your settings:

env
# Database
DB_FILE=storage/maishawatch.db

# JWT
JWT_SECRET_KEY=your-super-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480

# CORS
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# SMTP Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_USE_TLS=true

# Default Admin
DEFAULT_ADMIN_EMAIL=admin@maishawatch.com
DEFAULT_ADMIN_PASSWORD=Admin@123
🗄️ Database Setup
bash
# Run migrations
python scripts/migrate_db.py

# Seed initial data
python scripts/seed_data.py

# Import sample data
python scripts/import_data.py

# Sync all equipment
python scripts/sync_all_equipment.py
🚀 Running the Application
Method 1: Using run.py (Recommended)
bash
python run.py
Method 2: Using uvicorn directly
bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Verify Server
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
Access Swagger UI
Open browser: http://127.0.0.1:8000/docs

Test Authentication Flow
1. Login (First Time)
bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@maishawatch.com","password":"Admin@123"}'
2. Verify OTP
bash
# Get OTP from database (debug)
sqlite3 storage/maishawatch.db "SELECT otp FROM otp_store WHERE email='admin@maishawatch.com' ORDER BY created_at DESC LIMIT 1;"

# Verify OTP
curl -X POST http://localhost:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@maishawatch.com","otp":"123456"}'
3. Change Temporary Password
bash
curl -X POST http://localhost:8000/auth/change-temp-password \
  -H "Content-Type: application/json" \
  -d '{
    "email":"admin@maishawatch.com",
    "temp_password":"Admin@123",
    "new_password":"YourNewPassword123!",
    "confirm_password":"YourNewPassword123!"
  }'
4. Login with New Password
bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@maishawatch.com","password":"YourNewPassword123!"}'
📚 API Endpoints Reference
Authentication (/auth)
Method	Endpoint	Description
POST	/auth/login	Login with email/password
POST	/auth/verify-otp	Verify OTP
POST	/auth/change-temp-password	Change temporary password
GET	/auth/me	Get current user info
POST	/auth/logout	Logout
Equipment (/equipment)
Method	Endpoint	Description
GET	/equipment	List all equipment
POST	/equipment	Create equipment
GET	/equipment/{id}	Get equipment details
PUT	/equipment/{id}	Update equipment
DELETE	/equipment/{id}	Delete equipment
ML Predictions (/predict)
Method	Endpoint	Description
POST	/predict/failure/24h	Failure probability (24h)
POST	/predict/failure/72h	Failure probability (72h)
POST	/predict/failure/168h	Failure probability (168h)
POST	/predict/rul	Remaining Useful Life
Alerts (/alerts)
Method	Endpoint	Description
GET	/alerts	List alerts
POST	/alerts	Create alert
GET	/alerts/stats	Alert statistics
🔒 Security Model
Roles
system_administrator - Full system access

national_administrator - National operational management

national_executive - National read-only executive scope

facility_manager - One hospital/facility

biomedical_engineer - Equipment and maintenance

maintenance_technician - Assigned facility/equipment operations

clinician - Clinical equipment visibility

Scope Enforcement
Every protected endpoint derives identity and scope from the JWT. Facility-scoped users cannot retrieve another facility's equipment, alerts, maintenance history or work orders by changing an ID in the URL.

📧 Email Configuration
Gmail Setup
Enable 2-Factor Authentication

Generate App Password at https://myaccount.google.com/apppasswords

Use the generated password in .env

SMTP Variables
env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_USE_TLS=true
🔧 Troubleshooting
Common Issues
1. ModuleNotFoundError
bash
pip install -r requirements.txt
2. Database Error: "no such table"
bash
python scripts/migrate_db.py
3. SMTP Authentication Error
Use App Password for Gmail

Check your credentials

4. Port Already in Use
bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8000
kill -9 <PID>
📝 Quick Start Commands Summary
bash
# 1. Setup
python -m venv .venv
source .venv/bin/activate
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
📖 Additional Resources
FastAPI Documentation

SQLite Documentation

Scikit-learn Documentation

🤝 Contributing
Fork the repository

Create a feature branch (git checkout -b feature/amazing)

Commit changes (git commit -m 'Add amazing feature')

Push to branch (git push origin feature/amazing)

Open a Pull Request

📄 License
This project is proprietary and confidential.

🏁 Conclusion
Your MaishaWatch Backend is now fully set up and running! The system provides:

✅ Complete authentication with OTP and RBAC

✅ Equipment management with CSV sync

✅ ML-powered predictions and alerts

✅ Email notifications

✅ Real-time monitoring

✅ Complete audit trail

Ready for frontend integration! 🚀