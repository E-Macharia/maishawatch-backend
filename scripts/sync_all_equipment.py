# scripts/sync_all_equipment.py
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.data_service import sync_all_equipment_to_csv
from app.services.telemetry_service import TelemetrySimulator
from app.core.db import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_all_equipment():
    """Sync all equipment to CSV and generate missing telemetry"""
    print("=" * 60)
    print("Syncing All Equipment")
    print("=" * 60)

    # Step 1: Sync equipment to CSV
    print("\n📦 Syncing equipment to CSV...")
    result = sync_all_equipment_to_csv()
    print(f"✅ {result['synced']} equipment records synced")

    # Step 2: Check if sensor_telemetry table exists
    print("\n📊 Checking for equipment with missing telemetry...")

    with db() as c:
        # Check if sensor_telemetry table exists
        table_check = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_telemetry'"
        ).fetchone()

        if not table_check:
            print("⚠️  sensor_telemetry table doesn't exist. Creating it...")
            c.execute("""
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
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_equipment ON sensor_telemetry(equipment_id)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_timestamp ON sensor_telemetry(timestamp)"
            )
            print("✅ sensor_telemetry table created")

    # Step 3: Check for equipment without telemetry
    with db() as c:
        try:
            equipment_list = c.execute("""
                SELECT e.equipment_id, e.facility_id, e.equipment_type
                FROM equipment_registry e
                WHERE NOT EXISTS (
                    SELECT 1 FROM sensor_telemetry t 
                    WHERE t.equipment_id = e.equipment_id AND t.facility_id = e.facility_id
                )
            """).fetchall()
        except sqlite3.OperationalError as e:
            print(f"⚠️  Error querying sensor_telemetry: {e}")
            equipment_list = []

        if equipment_list:
            print(f"Found {len(equipment_list)} equipment with no telemetry data")

            for eq in equipment_list:
                eq_dict = dict(eq)
                print(f"  🔄 Generating telemetry for {eq_dict.get('equipment_id')}...")
                try:
                    TelemetrySimulator.generate_initial_readings(
                        eq_dict.get("equipment_id"),
                        eq_dict.get("facility_id"),
                        eq_dict.get("equipment_type") or "Unknown",
                        count=50,
                    )
                    print(f"  ✅ Telemetry generated for {eq_dict.get('equipment_id')}")
                except Exception as e:
                    print(
                        f"  ❌ Failed to generate telemetry for {eq_dict.get('equipment_id')}: {e}"
                    )
        else:
            print("✅ All equipment have telemetry data")

    print("\n" + "=" * 60)
    print("✅ Sync Complete!")
    print("=" * 60)


if __name__ == "__main__":
    sync_all_equipment()
