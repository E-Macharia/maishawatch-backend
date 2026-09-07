# scripts/migrate_db.py
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.paths import DB_FILE, STORAGE_DIR


def migrate():
    """Run database migrations to add sensor_telemetry table"""
    print(f"Using database: {DB_FILE}")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()

    # Check if sensor_telemetry table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_telemetry'"
    )
    if cursor.fetchone():
        print("ℹ️  sensor_telemetry table already exists")
    else:
        print("📦 Creating sensor_telemetry table...")
        cursor.execute("""
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
            )
        """)
        print("✅ sensor_telemetry table created")

    # Create indexes
    print("📦 Creating indexes...")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_equipment ON sensor_telemetry(equipment_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_timestamp ON sensor_telemetry(timestamp)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_facility ON sensor_telemetry(facility_id)"
    )
    print("✅ Indexes created")

    conn.commit()
    conn.close()

    print("✅ Migration completed successfully!")
    print(f"📁 Database location: {DB_FILE}")


if __name__ == "__main__":
    migrate()
