# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import CORS_ORIGINS
from app.core.db import db
from app.core.security import hash_password
from app.api.routers import (
    auth, users, facilities, equipment, maintenance, alerts,
    audit, notifications, reports, chat, dashboard,predictions,failure
)

app = FastAPI(
    title='MaishaWatch API',
    version='2.1.0',
    description='Secure predictive maintenance and hospital equipment operations API'
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

# Include routers
routers = [
    auth.router,
    users.router,
    facilities.router,
    equipment.router,
    maintenance.router,
    alerts.router,
    audit.router,
    notifications.router,
    reports.router,
    chat.router,
    dashboard.router,predictions.router,failure.router
]

for router in routers:
    app.include_router(router)

@app.on_event('startup')
def seed_default_admin():
    """Create default admin user if no users exist"""
    try:
        with db() as c:
            # Check if any users exist
            existing = c.execute('SELECT 1 FROM users LIMIT 1').fetchone()
            if existing:
                print("✅ Users already exist, skipping seed")
                return
            
            import os
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            email = os.getenv('DEFAULT_ADMIN_EMAIL', 'calebmunyeks002@gmail.com')
            password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin@123')
            
            c.execute('''
                INSERT INTO users 
                (id, name, email, password_hash, role, scope_type, scope_id, active, created_at, last_login, temp_password_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'USR-NATIONAL-ADMIN',
                'System Administrator',
                email,
                hash_password(password),
                'system_administrator',
                'national',
                None,
                1,
                now,
                now,
                1
            ))
            print(f"✅ Default admin created: {email} / {password}")
    except Exception as e:
        print(f"⚠️  Could not seed admin: {e}")

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'maishawatch-api', 'version': '2.1.0'}