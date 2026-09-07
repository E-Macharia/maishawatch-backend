import os
from app.core.paths import PROJECT_ROOT, DATA_DIR, STORAGE_DIR, DB_FILE

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-this-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_MINUTES = int(os.getenv('JWT_EXPIRE_MINUTES', '480'))
CORS_ORIGINS = [
    x.strip()
    for x in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if x.strip()
]
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com',)
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'watchmaisha@gmail.com',)
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'jqvdoycqscjywxmi',)
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USERNAME or 'watchmaisha@gmail.com',)
SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
