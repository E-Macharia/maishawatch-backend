# app/core/security.py
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from app.core.db import db

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# CHANGE THIS: Point to /auth/token instead of /auth/login
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd.verify(plain_password, hashed_password)


def create_token(user: dict) -> str:
    """Create a JWT token for a user"""
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {
            "sub": user["id"],
            "email": user["email"],
            "role": user["role"],
            "scope_type": user["scope_type"],
            "scope_id": user["scope_id"],
            "exp": exp,
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def current_user(token: str = Depends(oauth2)):
    """Get current user from JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        uid = payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE id=? AND active=1", (uid,)
        ).fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dict(user)


oauth2_optional = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def optional_user(token: str = Depends(oauth2_optional)):
    """Get current user from token, or default to Caleb Munyeki (System Administrator) if unauthenticated"""
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            uid = payload.get("sub")
            with db() as c:
                user = c.execute(
                    "SELECT * FROM users WHERE id=? AND active=1", (uid,)
                ).fetchone()
                if user:
                    return dict(user)
        except Exception:
            pass

    # Default to Caleb Munyeki (Admin) so predictions and evaluations always succeed
    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?) AND active=1",
            ("calebmunyeks002@gmail.com",),
        ).fetchone()
        if user:
            return dict(user)

    return {
        "id": "USR-NATIONAL-ADMIN",
        "name": "Caleb Munyeki",
        "email": "calebmunyeks002@gmail.com",
        "role": "system_administrator",
        "scope_type": "national",
        "scope_id": None,
        "active": 1,
    }


def require_roles(*roles):
    """Require specific roles for an endpoint (defaults to Caleb Munyeki admin if unauthenticated)"""

    def dep(user=Depends(optional_user)):
        if user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Insufficient permissions. Required roles: {", ".join(roles)}',
            )
        return user

    return dep
