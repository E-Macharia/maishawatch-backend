# app/services/telemetry_service.py
import random
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.core.paths import DATA_DIR
from app.services.data_service import read_csv, sync_telemetry_to_csv
import logging

logger = logging.getLogger(__name__)


class TelemetrySimulator:
    @staticmethod
    def get_equipment_type_parameters(equipment_type):
        """Get realistic parameters for equipment type"""
        parameters = {
            "MRI Machine": {
                "temp_base": 25.0,
                "temp_range": (20, 35),
                "vibration_base": 0.3,
                "vibration_range": (0.1, 1.0),
                "pressure_base": 100,
                "pressure_range": (95, 105),
                "power_base": 450,
                "power_range": (300, 600),
                "humidity_base": 40,
                "humidity_range": (30, 60),
            },
            "CT Scanner": {
                "temp_base": 22.0,
                "temp_range": (18, 30),
                "vibration_base": 0.2,
                "vibration_range": (0.05, 0.8),
                "pressure_base": 98,
                "pressure_range": (92, 102),
                "power_base": 350,
                "power_range": (200, 500),
                "humidity_base": 35,
                "humidity_range": (25, 55),
            },
            "Ventilator": {
                "temp_base": 24.0,
                "temp_range": (20, 30),
                "vibration_base": 0.1,
                "vibration_range": (0.02, 0.5),
                "pressure_base": 20,
                "pressure_range": (15, 30),
                "power_base": 150,
                "power_range": (100, 250),
                "humidity_base": 45,
                "humidity_range": (35, 65),
            },
            "Ultrasound Machine": {
                "temp_base": 23.0,
                "temp_range": (18, 28),
                "vibration_base": 0.15,
                "vibration_range": (0.05, 0.4),
                "pressure_base": 0,
                "pressure_range": (0, 0),
                "power_base": 200,
                "power_range": (150, 300),
                "humidity_base": 40,
                "humidity_range": (30, 50),
            },
            "Infusion Pump": {
                "temp_base": 22.0,
                "temp_range": (18, 26),
                "vibration_base": 0.05,
                "vibration_range": (0.01, 0.2),
                "pressure_base": 10,
                "pressure_range": (5, 15),
                "power_base": 50,
                "power_range": (30, 80),
                "humidity_base": 50,
                "humidity_range": (40, 60),
            },
            "Patient Monitor": {
                "temp_base": 23.0,
                "temp_range": (20, 28),
                "vibration_base": 0.08,
                "vibration_range": (0.02, 0.3),
                "pressure_base": 0,
                "pressure_range": (0, 0),
                "power_base": 100,
                "power_range": (50, 150),
                "humidity_base": 45,
                "humidity_range": (35, 55),
            },
            "X-Ray Machine": {
                "temp_base": 24.0,
                "temp_range": (20, 30),
                "vibration_base": 0.2,
                "vibration_range": (0.05, 0.6),
                "pressure_base": 0,
                "pressure_range": (0, 0),
                "power_base": 300,
                "power_range": (200, 400),
                "humidity_base": 35,
                "humidity_range": (25, 50),
            },
            "Surgical Equipment": {
                "temp_base": 20.0,
                "temp_range": (18, 25),
                "vibration_base": 0.15,
                "vibration_range": (0.05, 0.4),
                "pressure_base": 0,
                "pressure_range": (0, 0),
                "power_base": 250,
                "power_range": (150, 350),
                "humidity_base": 40,
                "humidity_range": (30, 50),
            },
            "Diagnostic Equipment": {
                "temp_base": 23.0,
                "temp_range": (20, 28),
                "vibration_base": 0.1,
                "vibration_range": (0.02, 0.3),
                "pressure_base": 0,
                "pressure_range": (0, 0),
                "power_base": 180,
                "power_range": (100, 250),
                "humidity_base": 40,
                "humidity_range": (30, 50),
            },
            "Anesthesia Machine": {
                "temp_base": 22.0,
                "temp_range": (18, 28),
                "vibration_base": 0.08,
                "vibration_range": (0.02, 0.3),
                "pressure_base": 15,
                "pressure_range": (10, 25),
                "power_base": 120,
                "power_range": (80, 200),
                "humidity_base": 50,
                "humidity_range": (40, 65),
            },
            "Dialysis Machine": {
                "temp_base": 24.0,
                "temp_range": (20, 30),
                "vibration_base": 0.12,
                "vibration_range": (0.05, 0.4),
                "pressure_base": 80,
                "pressure_range": (60, 100),
                "power_base": 200,
                "power_range": (150, 300),
                "humidity_base": 45,
                "humidity_range": (35, 55),
            },
            "Defibrillator": {
                "temp_base": 22.0,
                "temp_range": (18, 28),
                "vibration_base": 0.05,
                "vibration_range": (0.01, 0.2),
                "pressure_base": 0,
                "pressure_range": (0, 0),
                "power_base": 80,
                "power_range": (50, 150),
                "humidity_base": 45,
                "humidity_range": (35, 55),
            }
        }

        # Default parameters for unknown types
        default = {
            "temp_base": 22.0,
            "temp_range": (18, 30),
            "vibration_base": 0.15,
            "vibration_range": (0.02, 0.5),
            "pressure_base": 0,
            "pressure_range": (0, 0),
            "power_base": 150,
            "power_range": (100, 300),
            "humidity_base": 40,
            "humidity_range": (30, 60),
        }

        return parameters.get(equipment_type, default)

    @staticmethod
    def generate_reading(
        equipment_id, facility_id, equipment_type="Unknown", anomaly_probability=0.05
    ):
        """Generate a realistic sensor reading and sync to CSV"""
        params = TelemetrySimulator.get_equipment_type_parameters(equipment_type)

        # Generate base values with normal variation
        temperature = (
            params["temp_base"]
            + random.uniform(*params["temp_range"])
            - params["temp_base"]
        )
        vibration = (
            params["vibration_base"]
            + random.uniform(*params["vibration_range"])
            - params["vibration_base"]
        )
        pressure = (
            params["pressure_base"]
            + random.uniform(*params["pressure_range"])
            - params["pressure_base"]
            if params["pressure_base"] > 0
            else 0
        )
        power = (
            params["power_base"]
            + random.uniform(*params["power_range"])
            - params["power_base"]
        )
        humidity = (
            params["humidity_base"]
            + random.uniform(*params["humidity_range"])
            - params["humidity_base"]
        )

        # Add occasional anomalies
        if random.random() < anomaly_probability:
            anomaly_type = random.choice(
                ["temperature", "vibration", "power", "pressure"]
            )
            if anomaly_type == "temperature":
                temperature += random.uniform(5, 15)
            elif anomaly_type == "vibration":
                vibration += random.uniform(0.5, 2.0)
            elif anomaly_type == "power":
                power += random.uniform(100, 300)
            elif anomaly_type == "pressure" and pressure > 0:
                pressure += random.uniform(10, 30)

        # Calculate risk score based on deviations
        risk_score = 0.0

        # Temperature deviation
        temp_deviation = abs(temperature - params["temp_base"])
        if temp_deviation > 5:
            risk_score += min(0.3, (temp_deviation - 5) / 20)

        # Vibration deviation
        vib_deviation = vibration - params["vibration_base"]
        if vib_deviation > 0.3:
            risk_score += min(0.3, (vib_deviation - 0.3) / 1.0)

        # Power deviation
        power_deviation = abs(power - params["power_base"])
        if power_deviation > params["power_range"][1] * 0.2:
            risk_score += min(
                0.2,
                (power_deviation - params["power_range"][1] * 0.2)
                / (params["power_range"][1] * 0.5),
            )

        # Pressure deviation (if applicable)
        if pressure > 0:
            pressure_deviation = abs(pressure - params["pressure_base"])
            if pressure_deviation > 5:
                risk_score += min(0.2, (pressure_deviation - 5) / 20)

        risk_score = min(1.0, risk_score)

        # Determine operational status
        if risk_score >= 0.7:
            status = "CRITICAL"
        elif risk_score >= 0.4:
            status = "WARNING"
        else:
            status = "NORMAL"

        reading = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "equipment_id": equipment_id,
            "facility_id": facility_id,
            "equipment_type": equipment_type,
            "temperature": round(temperature, 2),
            "vibration": round(vibration, 3),
            "pressure": round(pressure, 1) if pressure > 0 else None,
            "power_consumption": round(power, 1),
            "humidity": round(humidity, 1),
            "risk_score": round(risk_score, 3),
            "operational_status": status,
            "anomaly": True if risk_score >= 0.4 else False,
        }

        # Sync to CSV immediately
        try:
            from app.services.data_service import sync_telemetry_to_csv
            sync_telemetry_to_csv(reading)
        except Exception as e:
            logger.error(f"Failed to sync telemetry to CSV: {e}")

        return reading

    @staticmethod
    def generate_batch(equipment_id, facility_id, count, equipment_type="Unknown"):
        """Generate a batch of historical telemetry data with CSV sync"""
        data = []
        start_time = datetime.now(timezone.utc) - timedelta(hours=count // 12)

        for i in range(count):
            timestamp = start_time + timedelta(minutes=i * 5)
            reading = TelemetrySimulator.generate_reading(
                equipment_id,
                facility_id,
                equipment_type,
                anomaly_probability=(
                    0.03 if i < count * 0.8 else 0.08
                ),
            )
            reading["timestamp"] = timestamp.isoformat()
            data.append(reading)

        return data

    @staticmethod
    def generate_initial_readings(
        equipment_id, facility_id, equipment_type="Unknown", count=100
    ):
        """Generate initial readings for new equipment with CSV sync and database storage"""
        import sqlite3
        from app.core.paths import DB_FILE
        
        logger.info(f"Generating {count} initial readings for {equipment_id}")
        
        data = []
        start_time = datetime.now(timezone.utc) - timedelta(hours=count // 12)

        for i in range(count):
            timestamp = start_time + timedelta(minutes=i * 5)
            reading = TelemetrySimulator.generate_reading(
                equipment_id,
                facility_id,
                equipment_type,
                anomaly_probability=(
                    0.02 if i < count * 0.8 else 0.08
                ),
            )
            reading["timestamp"] = timestamp.isoformat()
            data.append(reading)

        # Save to CSV
        df = pd.DataFrame(data)
        file_path = DATA_DIR / "sensor_telemetry.csv"

        if file_path.exists():
            existing = pd.read_csv(file_path)
            combined = pd.concat([existing, df], ignore_index=True)
            if len(combined) > 10000:
                combined = combined.groupby('equipment_id').tail(10000)
            combined.to_csv(file_path, index=False)
        else:
            df.to_csv(file_path, index=False)

        # Save to database
        try:
            conn = sqlite3.connect(str(DB_FILE))
            cursor = conn.cursor()
            
            for reading in data:
                cursor.execute('''
                    INSERT INTO sensor_telemetry 
                    (timestamp, equipment_id, facility_id, equipment_type, 
                     temperature, vibration, pressure, humidity, power_consumption, 
                     risk_score, operational_status, anomaly)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    reading.get('timestamp'),
                    reading.get('equipment_id'),
                    reading.get('facility_id'),
                    reading.get('equipment_type'),
                    reading.get('temperature'),
                    reading.get('vibration'),
                    reading.get('pressure'),
                    reading.get('humidity'),
                    reading.get('power_consumption'),
                    reading.get('risk_score'),
                    reading.get('operational_status'),
                    1 if reading.get('anomaly') else 0
                ))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved {len(data)} readings to database for {equipment_id}")
        except Exception as e:
            logger.error(f"Failed to save telemetry to database: {e}")

        logger.info(f"Generated {len(data)} initial readings for {equipment_id}")
        return data

    @staticmethod
    def start_simulation(
        equipment_id, facility_id, equipment_type, interval_seconds=60
    ):
        """Start continuous telemetry simulation in background with auto-sync"""

        def simulate():
            from app.engines.alert_engine import evaluate_and_create_alert
            import time

            logger.info(f"Starting telemetry simulation for {equipment_id}")

            while True:
                try:
                    # Generate reading (auto-syncs to CSV)
                    reading = TelemetrySimulator.generate_reading(
                        equipment_id, facility_id, equipment_type
                    )

                    # Trigger evaluation
                    try:
                        evaluate_and_create_alert(equipment_id, facility_id)
                    except Exception as e:
                        logger.error(f"Alert evaluation failed for {equipment_id}: {e}")

                    time.sleep(interval_seconds)
                except Exception as e:
                    logger.error(f"Telemetry simulation error for {equipment_id}: {e}")
                    time.sleep(interval_seconds)

        import threading

        thread = threading.Thread(target=simulate, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def sync_existing_equipment_telemetry():
        """Generate telemetry for equipment that has none"""
        from app.core.db import db
        
        logger.info("Checking for equipment without telemetry...")
        
        with db() as c:
            equipment_list = c.execute('''
                SELECT e.equipment_id, e.facility_id, e.equipment_type
                FROM equipment_registry e
                WHERE NOT EXISTS (
                    SELECT 1 FROM sensor_telemetry t 
                    WHERE t.equipment_id = e.equipment_id AND t.facility_id = e.facility_id
                )
            ''').fetchall()
            
            if not equipment_list:
                logger.info("All equipment have telemetry data")
                return {'generated': 0, 'equipment': []}
            
            generated = []
            for eq in equipment_list:
                eq_dict = dict(eq)
                try:
                    logger.info(f"Generating telemetry for {eq_dict.get('equipment_id')}...")
                    TelemetrySimulator.generate_initial_readings(
                        eq_dict.get('equipment_id'),
                        eq_dict.get('facility_id'),
                        eq_dict.get('equipment_type') or 'Unknown',
                        count=50
                    )
                    generated.append(eq_dict.get('equipment_id'))
                except Exception as e:
                    logger.error(f"Failed to generate telemetry for {eq_dict.get('equipment_id')}: {e}")
            
            return {'generated': len(generated), 'equipment': generated}