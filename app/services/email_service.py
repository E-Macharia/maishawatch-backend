# app/services/email_service.py
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_FROM,
    SMTP_USE_TLS,
)
import logging

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, html_body: str = None):
    """Send an email using SMTP configuration"""
    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("SMTP not fully configured")
        return False, "SMTP is not fully configured"

    sender = SMTP_FROM or SMTP_USERNAME

    # Create message
    if html_body:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to

        # Attach both plain text and HTML versions
        part1 = MIMEText(body, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)
    else:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.set_content(body)

    try:
        logger.info(f"Sending email to {to}: {subject}")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"✅ Email sent to {to}")
        return True, "sent"

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False, f"SMTP authentication failed: {e}"
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False, f"SMTP error: {e}"
    except OSError as e:
        logger.error(f"SMTP connection error: {e}")
        return False, f"SMTP connection error: {e}"
    except Exception as e:
        logger.error(f"Email delivery error: {e}")
        return False, f"Email delivery error: {e}"


def send_html_email(to: str, subject: str, html_content: str, text_content: str = None):
    """Send an HTML email with plain text fallback"""
    if not text_content:
        # Strip HTML tags for plain text fallback
        import re

        text_content = re.sub(r"<[^>]+>", " ", html_content)
        text_content = re.sub(r"\s+", " ", text_content).strip()

    return send_email(to, subject, text_content, html_content)


def send_welcome_email(
    email: str, name: str, temp_password: str, site_url: str = "http://localhost:5173"
):
    """Send welcome email to new user"""
    subject = "Welcome to MaishaWatch - Your Account Has Been Created"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #0066cc; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background: #f9f9f9; }}
            .credentials {{ background: #e8f4f8; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .button {{ display: inline-block; background: #0066cc; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; }}
            .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to MaishaWatch</h1>
                <p>Your Account Has Been Created</p>
            </div>
            <div class="content">
                <h2>Hello {name},</h2>
                <p>Your MaishaWatch account has been created successfully!</p>
                
                <div class="credentials">
                    <h3>Your Login Credentials:</h3>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Temporary Password:</strong> {temp_password}</p>
                    <p style="color: #ff6600; font-weight: bold;">⚠️ This is a temporary password. You will be required to change it upon first login.</p>
                </div>
                
                <p>To access your account, please follow these steps:</p>
                <ol>
                    <li>Click the button below to go to the login page</li>
                    <li>Enter your email and temporary password</li>
                    <li>You will receive an OTP via email for verification</li>
                    <li>After OTP verification, you will be prompted to change your password</li>
                    <li>Set your new password and login with it</li>
                </ol>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{site_url}" class="button">Go to Login Page</a>
                </div>
                
                <p>If you have any questions or need assistance, please contact your system administrator.</p>
                <p>Thank you for choosing MaishaWatch!</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 MaishaWatch. All rights reserved.</p>
                <p>This is an automated message, please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"""
    Welcome to MaishaWatch - Your Account Has Been Created
    
    Hello {name},
    
    Your MaishaWatch account has been created successfully!
    
    Your Login Credentials:
    Email: {email}
    Temporary Password: {temp_password}
    
    ⚠️ This is a temporary password. You will be required to change it upon first login.
    
    To access your account, please follow these steps:
    1. Go to the login page: {site_url}
    2. Enter your email and temporary password
    3. You will receive an OTP via email for verification
    4. After OTP verification, you will be prompted to change your password
    5. Set your new password and login with it
    
    If you have any questions or need assistance, please contact your system administrator.
    
    Thank you for choosing MaishaWatch!
    
    --
    MaishaWatch Team
    """

    return send_html_email(email, subject, html_body, text_body)


def send_otp_email(email: str, otp: str, purpose: str = "login"):
    """Send OTP verification email"""
    purpose_names = {
        "login": "Login",
        "first_time": "First Time Login",
        "password_reset": "Password Reset",
    }

    purpose_name = purpose_names.get(purpose, "Verification")
    subject = f"MaishaWatch - {purpose_name} OTP"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #0066cc; color: white; padding: 20px; text-align: center; }}
            .otp-box {{ background: #e8f4f8; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 10px; margin: 20px 0; border-radius: 5px; }}
            .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>MaishaWatch</h1>
                <p>{purpose_name} OTP Verification</p>
            </div>
            <div class="content">
                <p>Your OTP for {purpose_name.lower()} is:</p>
                <div class="otp-box">{otp}</div>
                <p>This OTP will expire in <strong>10 minutes</strong>.</p>
                <p>If you did not request this, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 MaishaWatch. All rights reserved.</p>
                <p>This is an automated message, please do not reply.</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"""
    MaishaWatch - {purpose_name} OTP
    
    Your OTP for {purpose_name.lower()} is: {otp}
    
    This OTP will expire in 10 minutes.
    
    If you did not request this, please ignore this email.
    
    --
    MaishaWatch Team
    """

    return send_html_email(email, subject, html_body, text_body)
