# scripts/import_data.py
import sys
from pathlib import Path
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.data_service import (
    sync_equipment_from_csv,
    sync_telemetry_from_csv,
    clear_cache,
)
from app.services.telemetry_service import TelemetrySimulator
from app.core.db import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def import_all_data():
    """Import all data from CSV files"""
    logger.info("=" * 60)
    logger.info("Starting data import...")
    logger.info("=" * 60)

    # Clear cache
    clear_cache()

    # Sync equipment
    logger.info("\n📦 Syncing equipment...")
    eq_result = sync_equipment_from_csv()
    logger.info(f"Equipment sync result: {eq_result}")

    # Sync telemetry
    logger.info("\n📊 Syncing telemetry...")
    tel_result = sync_telemetry_from_csv()
    logger.info(f"Telemetry sync result: {tel_result}")

    # Generate initial readings for equipment without telemetry
    logger.info("\n🔄 Generating initial readings for equipment without telemetry...")

    with db() as c:
        equipment_list = c.execute("""
            SELECT e.equipment_id, e.facility_id, e.equipment_type
            FROM equipment_registry e
            LEFT JOIN sensor_telemetry t ON e.equipment_id = t.equipment_id AND e.facility_id = t.facility_id
            WHERE t.equipment_id IS NULL
        """).fetchall()

        generated = 0
        for eq in equipment_list:
            logger.info(f"  Generating readings for {eq['equipment_id']}...")
            TelemetrySimulator.generate_initial_readings(
                eq["equipment_id"], eq["facility_id"], eq["equipment_type"], count=50
            )
            generated += 1

        logger.info(f"Generated initial readings for {generated} equipment")

    logger.info("\n" + "=" * 60)
    logger.info("✅ Data import completed!")
    logger.info("=" * 60)


def import_equipment_only():
    """Import only equipment data"""
    logger.info("Importing equipment data...")
    result = sync_equipment_from_csv()
    logger.info(f"Result: {result}")
    return result


def import_telemetry_only():
    """Import only telemetry data"""
    logger.info("Importing telemetry data...")
    result = sync_telemetry_from_csv()
    logger.info(f"Result: {result}")
    return result


if __name__ == "__main__":
    import_all_data()
