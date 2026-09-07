# app/api/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from uuid import uuid4
from datetime import datetime, timezone
import os
from app.core.db import db
from app.core.security import hash_password, require_roles, current_user
from app.core.audit import audit
from app.services.email_service import send_welcome_email

ROLES = ['system_administrator', 'national_administrator', 'national_executive', 
         'facility_manager', 'biomedical_engineer', 'maintenance_technician', 'clinician']

router = APIRouter(prefix='/users', tags=['User Management'])

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    scope_type: str = 'facility'
    scope_id: str | None = None

class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    active: bool | None = None

@router.get('')
def list_users(u=Depends(require_roles('system_administrator', 'national_administrator', 'national_executive'))):
    with db() as c:
        rows = [dict(x) for x in c.execute('''
            SELECT id, name, email, role, scope_type, scope_id, active, created_at, last_login 
            FROM users ORDER BY name
        ''')]
    
    if u['role'] != 'system_administrator' and u['scope_type'] != 'national':
        rows = [x for x in rows if x['scope_id'] == u['scope_id']]
    
    return rows

@router.post('')
def create_user(x: UserCreate, u=Depends(require_roles('system_administrator', 'national_administrator'))):
    # Validate role
    if x.role not in ROLES:
        raise HTTPException(400, f'Unsupported role. Allowed: {", ".join(ROLES)}')
    
    # Check permissions
    if u['role'] != 'system_administrator' and x.scope_type == 'national':
        raise HTTPException(403, 'Only system administrator can create national-scope users')
    
    if u['scope_type'] != 'national' and x.scope_id != u['scope_id']:
        raise HTTPException(403, 'User must be assigned within your facility')
    
    # Create user
    uid = 'USR-' + uuid4().hex[:8].upper()
    now = datetime.now(timezone.utc).isoformat()
    
    with db() as c:
        try:
            c.execute('''
                INSERT INTO users 
                (id, name, email, password_hash, role, scope_type, scope_id, active, created_at, last_login, temp_password_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (uid, x.name, x.email, hash_password(x.password), x.role, x.scope_type, x.scope_id, 1, now, None, 0))
        except Exception as e:
            raise HTTPException(409, f'Email already registered: {str(e)}')
    
    # Audit
    audit(u, 'CREATE_USER', 'user', uid, {
        'role': x.role, 
        'scope_id': x.scope_id,
        'email': x.email
    })
    
    # Send welcome email
    try:
        site_url = os.getenv('SITE_URL', 'http://localhost:5173')
        success, message = send_welcome_email(x.email, x.name, x.password, site_url)
        if success:
            print(f"✅ Welcome email sent to {x.email}")
        else:
            print(f"⚠️ Could not send welcome email to {x.email}: {message}")
    except Exception as e:
        print(f"⚠️ Error sending welcome email to {x.email}: {e}")
    
    return {
        'id': uid,
        'message': 'User created successfully. Welcome email sent.',
        'email_sent': True
    }

@router.patch('/{user_id}')
def update_user(user_id: str, x: UserUpdate, u=Depends(require_roles('system_administrator', 'national_administrator'))):
    fields = []
    vals = []
    
    for k, v in x.model_dump(exclude_none=True).items():
        fields.append(k + '=?')
        vals.append(int(v) if k == 'active' else v)
    
    if not fields:
        return {'message': 'No changes'}
    
    vals.append(user_id)
    
    with db() as c:
        if not c.execute('SELECT 1 FROM users WHERE id=?', (user_id,)).fetchone():
            raise HTTPException(404, 'User not found')
        c.execute('UPDATE users SET ' + ','.join(fields) + ' WHERE id=?', vals)
    
    audit(u, 'UPDATE_USER', 'user', user_id, x.model_dump(exclude_none=True))
    
    # If user was deactivated, send notification
    if x.active is False:
        with db() as c:
            user = c.execute('SELECT email, name FROM users WHERE id=?', (user_id,)).fetchone()
            if user:
                try:
                    from app.services.email_service import send_email
                    subject = "MaishaWatch - Account Deactivated"
                    body = f"""
                    Hello {user['name']},
                    
                    Your MaishaWatch account has been deactivated by an administrator.
                    
                    If you believe this is an error, please contact your system administrator.
                    
                    Thank you,
                    MaishaWatch Team
                    """
                    send_email(user['email'], subject, body)
                except Exception:
                    pass
    
    return {'message': 'User updated'}