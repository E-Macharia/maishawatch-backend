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

# AI & LLM Configuration
AI_API_KEY = os.getenv('AI_API_KEY') or os.getenv('GROQ_API_KEY') or os.getenv('OPENAI_API_KEY') or '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'
AI_MODEL = os.getenv('AI_MODEL') or os.getenv('GROQ_MODEL') or 'llama-3.3-70b-versatile'
AI_BASE_URL = os.getenv('AI_BASE_URL')
if not AI_BASE_URL:
    if AI_API_KEY and AI_API_KEY.startswith('gsk_'):
        AI_BASE_URL = 'https://api.groq.com/openai/v1/chat/completions'
    elif AI_API_KEY and AI_API_KEY.startswith('sk-ant-'):
        AI_BASE_URL = 'https://api.anthropic.com/v1/messages'
    else:
        AI_BASE_URL = 'https://api.openai.com/v1/chat/completions'
