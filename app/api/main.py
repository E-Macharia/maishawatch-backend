# app/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import CORS_ORIGINS
from app.core.db import db
from app.core.security import hash_password, optional_user
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
    """Ensure default admin user (Evans Macharia) exists and is active"""
    try:
        with db() as c:
            import os
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            email = os.getenv('DEFAULT_ADMIN_EMAIL', 'machariaevans636@gmail.com').strip()
            password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin@123').strip()

            # Check if this admin email already exists
            admin_user = c.execute(
                'SELECT * FROM users WHERE lower(email)=lower(?)', (email,)
            ).fetchone()

            if not admin_user:
                # Check if old admin exists to update, or create new record
                old_admin = c.execute(
                    "SELECT * FROM users WHERE id='USR-NATIONAL-ADMIN' OR lower(email)='calebmunyeks002@gmail.com'"
                ).fetchone()

                if old_admin:
                    c.execute('''
                        UPDATE users
                        SET email=?, name=?, password_hash=?, active=1, temp_password_used=1, role='system_administrator', scope_type='national'
                        WHERE id=?
                    ''', (email, 'Evans Macharia', hash_password(password), old_admin['id']))
                    print(f"✅ Admin user updated to: {email}")
                else:
                    c.execute('''
                        INSERT INTO users 
                        (id, name, email, password_hash, role, scope_type, scope_id, active, created_at, last_login, temp_password_used)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        'USR-NATIONAL-ADMIN',
                        'Evans Macharia',
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
            else:
                # Ensure active and updated role
                c.execute(
                    "UPDATE users SET active=1, role='system_administrator', scope_type='national' WHERE lower(email)=lower(?)",
                    (email,)
                )
                print(f"✅ National admin {email} verified active.")
    except Exception as e:
        print(f"⚠️  Could not seed admin: {e}")

@app.api_route('/', methods=['GET', 'HEAD'])
def root():
    return {
        'message': 'Welcome to MaishaWatch API',
        'status': 'online',
        'version': '2.1.0',
        'docs': '/docs',
        'health': '/health'
    }

@app.api_route('/health', methods=['GET', 'HEAD'])
def health():
    return {'status': 'ok', 'service': 'maishawatch-api', 'version': '2.1.0'}

@app.get('/analytics/summary', tags=['Dashboard'])
def analytics_summary(u=Depends(optional_user)):
    return dashboard.dashboard_summary(u)