# app/core/db.py
import sqlite3
from contextlib import contextmanager
from app.core.paths import DB_FILE, STORAGE_DIR

STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Fixed SCHEMA - removed all comments with # inside the SQL
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS hospitals (
    facility_id TEXT PRIMARY KEY,
    facility_name TEXT NOT NULL,
    county TEXT NOT NULL,
    keph_level TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    created_by TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id TEXT,
    actor_email TEXT,
    actor_role TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    scope_id TEXT,
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_work_orders (
    id TEXT PRIMARY KEY,
    equipment_id TEXT NOT NULL,
    facility_id TEXT,
    assigned_to TEXT,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    scheduled_at TEXT,
    completed_at TEXT,
    resolution TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    email TEXT,
    subject TEXT,
    body TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    sent_at TEXT,
    notification_type TEXT,
    read_at TEXT
);

CREATE TABLE IF NOT EXISTS equipment_registry (
    equipment_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    equipment_type TEXT NOT NULL,
    manufacturer TEXT,
    model TEXT,
    serial_number TEXT,
    status TEXT NOT NULL DEFAULT 'OPERATIONAL',
    installation_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (equipment_id, facility_id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    alert_type TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'MANUAL',
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    recommendation TEXT,
    equipment_id TEXT,
    facility_id TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT
);

CREATE TABLE IF NOT EXISTS otp_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    otp TEXT NOT NULL,
    purpose TEXT NOT NULL,
    expiry TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sensor_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    equipment_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    equipment_type TEXT,
    temperature REAL,
    vibration REAL,
    pressure REAL,
    humidity REAL,
    power_consumption REAL,
    risk_score REAL,
    operational_status TEXT,
    anomaly INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_equipment_registry_facility ON equipment_registry(facility_id);
CREATE INDEX IF NOT EXISTS idx_equipment_registry_equipment ON equipment_registry(equipment_id);
CREATE INDEX IF NOT EXISTS idx_hospitals_county ON hospitals(county);
CREATE INDEX IF NOT EXISTS idx_users_scope ON users(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notification_queue(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notification_queue(user_id, read_at);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notification_queue(notification_type);
CREATE INDEX IF NOT EXISTS idx_alerts_facility ON alerts(facility_id);
CREATE INDEX IF NOT EXISTS idx_alerts_equipment ON alerts(equipment_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts(source);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_otp_store_email ON otp_store(email);
CREATE INDEX IF NOT EXISTS idx_otp_store_purpose ON otp_store(purpose);
CREATE INDEX IF NOT EXISTS idx_otp_store_expiry ON otp_store(expiry);
CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_equipment ON sensor_telemetry(equipment_id);
CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_timestamp ON sensor_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_facility ON sensor_telemetry(facility_id);
"""

def _migrate(c):
    """Apply migrations to existing database tables"""
    # Check and migrate notification_queue
    cols = {r['name'] for r in c.execute('PRAGMA table_info(notification_queue)').fetchall()}
    if 'notification_type' not in cols:
        c.execute('ALTER TABLE notification_queue ADD COLUMN notification_type TEXT')
        print("✅ Added notification_type column to notification_queue")
    if 'read_at' not in cols:
        c.execute('ALTER TABLE notification_queue ADD COLUMN read_at TEXT')
        print("✅ Added read_at column to notification_queue")
    
    # Check and migrate alerts
    alert_cols = {r['name'] for r in c.execute('PRAGMA table_info(alerts)').fetchall()}
    if 'source' not in alert_cols:
        c.execute("ALTER TABLE alerts ADD COLUMN source TEXT NOT NULL DEFAULT 'MANUAL'")
        print("✅ Added source column to alerts")
    
    # Check and migrate users
    user_cols = {r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
    if 'temp_password_used' not in user_cols:
        c.execute('ALTER TABLE users ADD COLUMN temp_password_used INTEGER DEFAULT 0')
        print("✅ Added temp_password_used column to users")

@contextmanager
def db():
    """Database connection context manager"""
    c = sqlite3.connect(str(DB_FILE), timeout=30)
    c.row_factory = sqlite3.Row
    try:
        c.execute('PRAGMA busy_timeout=30000')
        c.execute('PRAGMA foreign_keys=ON')
        c.executescript(SCHEMA)
        _migrate(c)
        yield c
        c.commit()
    except Exception as e:
        c.rollback()
        print(f"❌ Database error: {e}")
        raise
    finally:
        c.close()