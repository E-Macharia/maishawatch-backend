# app/api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timezone, timedelta
import secrets
from app.core.db import db
from app.core.security import verify_password, create_token, current_user, optional_user, hash_password
from app.core.audit import audit
from app.services.email_service import send_email
from fastapi.security import OAuth2PasswordRequestForm
router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Models ---
class Login(BaseModel):
    email: EmailStr
    password: str


class OTPVerification(BaseModel):
    email: EmailStr
    otp: str


class ChangePassword(BaseModel):
    email: EmailStr
    temp_password: str
    new_password: str = Field(min_length=8)
    confirm_password: str


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(min_length=8)
    confirm_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
    confirm_password: str


# --- Helper Functions ---
def generate_otp():
    return "".join(secrets.choice("0123456789") for _ in range(6))


def store_otp(email: str, otp: str, purpose: str = "login"):
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    with db() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO otp_store (email, otp, purpose, expiry, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (email, otp, purpose, expiry, datetime.now(timezone.utc).isoformat()),
        )


def verify_otp(email: str, otp: str, purpose: str = "login"):
    with db() as c:
        row = c.execute(
            """
            SELECT otp, expiry FROM otp_store 
            WHERE email = ? AND purpose = ? 
            ORDER BY created_at DESC LIMIT 1
        """,
            (email, purpose),
        ).fetchone()
        if not row:
            return False
        if row["otp"] != otp:
            return False
        if datetime.now(timezone.utc).isoformat() > row["expiry"]:
            return False
        return True


# --- Endpoints ---
@router.post("/token")
def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    background_tasks: BackgroundTasks = None,
):
    """OAuth2 compatible login endpoint for Swagger UI"""
    print(f"🔐 OAuth2 Login attempt: {form_data.username}")

    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?)", (form_data.username,)
        ).fetchone()

    if not user:
        print(f"❌ User not found: {form_data.username}")
        raise HTTPException(401, "Invalid email or password")

    if not user["active"]:
        print(f"❌ User inactive: {form_data.username}")
        raise HTTPException(401, "Invalid email or password")

    user_dict = dict(user)

    if not verify_password(form_data.password, user_dict["password_hash"]):
        print(f"❌ Wrong password for: {form_data.username}")
        raise HTTPException(401, "Invalid email or password")

    print(f"✅ Login successful for: {form_data.username}")

    # Check if first time login (system administrators bypass OTP for direct OAuth2/Swagger access)
    is_first_time = (
        user_dict["last_login"] is None and user_dict.get("temp_password_used", 0) == 0
    )

    if is_first_time and user_dict.get("role") != "system_administrator":
        # For first time login, return a special response
        # The OAuth2 flow expects a token, so we'll return an error with instructions
        raise HTTPException(
            403,
            detail="First time login requires OTP verification. Please use /auth/login endpoint.",
        )

    # Regular login - create token
    token = create_token(user_dict)

    # Update last login
    now = datetime.now(timezone.utc).isoformat()
    with db() as c:
        c.execute("UPDATE users SET last_login=? WHERE id=?", (now, user_dict["id"]))

    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(x: Login, background_tasks: BackgroundTasks):
    print(f"🔐 Login attempt: {x.email}")

    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?)", (x.email,)
        ).fetchone()

    if not user:
        print(f"❌ User not found: {x.email}")
        raise HTTPException(401, "Invalid email or password")

    if not user["active"]:
        print(f"❌ User inactive: {x.email}")
        raise HTTPException(401, "Invalid email or password")

    user_dict = dict(user)

    if not verify_password(x.password, user_dict["password_hash"]):
        print(f"❌ Wrong password for: {x.email}")
        raise HTTPException(401, "Invalid email or password")

    print(f"✅ Login successful for: {x.email}")

    is_first_time = (
        user_dict["last_login"] is None and user_dict.get("temp_password_used", 0) == 0
    )

    otp = generate_otp()
    purpose = "first_time" if is_first_time else "login"
    store_otp(x.email, otp, purpose)

    body = f"""
    MaishaWatch {purpose.replace('_', ' ').title()} OTP
    
    Your OTP is: {otp}
    
    This OTP will expire in 10 minutes.
    
    If you did not request this, please ignore this email.
    
    MaishaWatch Team
    """
    background_tasks.add_task(
        send_email,
        x.email,
        f'MaishaWatch - {purpose.replace("_", " ").title()} OTP',
        body,
    )

    print(f"📧 OTP sent to {x.email}: {otp} (for debugging)")

    return {
        "requires_otp": True,
        "is_first_time": is_first_time,
        "message": "OTP sent to your email",
        "email": x.email,
        "otp_for_debug": otp,
    }


@router.post("/verify-otp")
def verify_otp_endpoint(x: OTPVerification):
    print(f"🔐 Verifying OTP for: {x.email}")
    print(f"🔑 OTP: {x.otp}")

    if not verify_otp(x.email, x.otp, "login") and not verify_otp(
        x.email, x.otp, "first_time"
    ):
        print(f"❌ Invalid OTP for: {x.email}")
        raise HTTPException(400, "Invalid or expired OTP")

    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?)", (x.email,)
        ).fetchone()
        if not user:
            raise HTTPException(404, "User not found")

        user_dict = dict(user)
        is_first = (
            user_dict["last_login"] is None
            and user_dict.get("temp_password_used", 0) == 0
        )

        print(f"✅ OTP verified for: {x.email}")
        print(f"📋 First time: {is_first}")

        now = datetime.now(timezone.utc).isoformat()
        c.execute("UPDATE users SET last_login=? WHERE id=?", (now, user_dict["id"]))

        if is_first:
            c.execute(
                "UPDATE users SET temp_password_used=1 WHERE id=?", (user_dict["id"],)
            )

        c.execute("DELETE FROM otp_store WHERE email=?", (x.email,))

    audit(user_dict, "OTP_VERIFIED", "auth", user_dict["id"])

    if is_first:
        return {
            "verified": True,
            "requires_password_change": True,
            "message": "OTP verified. Please change your temporary password.",
            "email": x.email,
            "user": {
                "id": user_dict["id"],
                "name": user_dict["name"],
                "email": user_dict["email"],
                "role": user_dict["role"],
                "scope_type": user_dict["scope_type"],
                "scope_id": user_dict["scope_id"],
            },
        }

    token = create_token(user_dict)
    return {
        "verified": True,
        "requires_password_change": False,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_dict["id"],
            "name": user_dict["name"],
            "email": user_dict["email"],
            "role": user_dict["role"],
            "scope_type": user_dict["scope_type"],
            "scope_id": user_dict["scope_id"],
        },
    }


@router.post("/change-temp-password")
def change_temp_password(x: ChangePassword):
    print(f"🔄 Changing password for: {x.email}")

    if x.new_password != x.confirm_password:
        raise HTTPException(400, "Passwords do not match")

    if len(x.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?)", (x.email,)
        ).fetchone()
        if not user:
            raise HTTPException(404, "User not found")

        user_dict = dict(user)

        if not verify_password(x.temp_password, user_dict["password_hash"]):
            raise HTTPException(400, "Invalid temporary password")

        new_hash = hash_password(x.new_password)
        c.execute(
            "UPDATE users SET password_hash=?, temp_password_used=1 WHERE id=?",
            (new_hash, user_dict["id"]),
        )

    audit(user_dict, "PASSWORD_CHANGED", "auth", user_dict["id"])

    print(f"✅ Password changed for: {x.email}")

    return {
        "message": "Password changed successfully. Please login with your new credentials.",
        "email": x.email,
    }


@router.post("/forgot-password")
def forgot_password(x: ForgotPassword, background_tasks: BackgroundTasks):
    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?)", (x.email,)
        ).fetchone()
        if not user:
            raise HTTPException(404, "Email not found")

    otp = generate_otp()
    store_otp(x.email, otp, "password_reset")

    body = f"""
    MaishaWatch - Password Reset
    
    You requested to reset your password. Please use the following OTP:
    
    OTP: {otp}
    
    This OTP will expire in 10 minutes.
    
    If you did not request this, please ignore this email.
    
    MaishaWatch Team
    """
    background_tasks.add_task(
        send_email, x.email, "MaishaWatch - Password Reset OTP", body
    )

    return {"message": "OTP sent to your email", "email": x.email}


@router.post("/reset-password")
def reset_password(x: ResetPassword):
    if x.new_password != x.confirm_password:
        raise HTTPException(400, "Passwords do not match")

    if len(x.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    if not verify_otp(x.email, x.otp, "password_reset"):
        raise HTTPException(400, "Invalid or expired OTP")

    with db() as c:
        user = c.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?)", (x.email,)
        ).fetchone()
        if not user:
            raise HTTPException(404, "User not found")

        new_hash = hash_password(x.new_password)
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user["id"]))
        c.execute("DELETE FROM otp_store WHERE email=?", (x.email,))

    audit(user, "PASSWORD_RESET", "auth", user["id"])

    return {
        "message": "Password reset successfully. Please login with your new password."
    }


@router.post("/change-password")
def change_password(x: PasswordChange, u=Depends(current_user)):
    if x.new_password != x.confirm_password:
        raise HTTPException(400, "Passwords do not match")

    if len(x.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    with db() as c:
        user = c.execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
        if not user:
            raise HTTPException(404, "User not found")

        if not verify_password(x.current_password, user["password_hash"]):
            raise HTTPException(400, "Current password is incorrect")

        new_hash = hash_password(x.new_password)
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user["id"]))

    audit(u, "PASSWORD_CHANGED", "auth", u["id"])

    return {"message": "Password changed successfully"}


@router.get("/me")
def me(u=Depends(optional_user)):
    with db() as c:
        user = c.execute(
            "SELECT id, name, email, role, scope_type, scope_id, last_login, created_at FROM users WHERE id=?",
            (u["id"],),
        ).fetchone()
    return dict(user) if user else u


@router.post("/logout")
def logout(u=Depends(optional_user)):
    audit(u, "LOGOUT", "auth", u["id"])
    return {"message": "Signed out"}
