# app/services/data_service.py
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from app.core.paths import DATA_DIR
from app.core.db import db
import logging

logger = logging.getLogger(__name__)

_cache = {}
_cache_timestamp = {}


def clear_cache():
    """Clear all cached data"""
    _cache.clear()
    _cache_timestamp.clear()


def read_csv(name, refresh=False):
    """Read CSV file with caching"""
    cache_key = name
    if refresh or cache_key not in _cache:
        p = DATA_DIR / name
        if not p.exists():
            logger.warning(f"CSV file not found: {p}")
            return pd.DataFrame()
        try:
            _cache[cache_key] = pd.read_csv(p)
            _cache_timestamp[cache_key] = datetime.now(timezone.utc).isoformat()
            logger.info(f"Loaded CSV: {name} ({len(_cache[cache_key])} rows)")
        except Exception as e:
            logger.error(f"Error loading CSV {name}: {e}")
            return pd.DataFrame()
    return _cache[cache_key].copy()


def facilities():
    """Get facilities from database and CSV"""
    rows = {}

    # Read from CSV
    e = read_csv("equipment_master.csv")
    if not e.empty:
        g = (
            e.groupby(["facility_id", "facility", "county", "keph_level"], dropna=False)
            .agg(
                equipment_count=("equipment_id", "count"),
                equipment_types=(
                    "equipment_type",
                    lambda x: ", ".join(sorted(set(map(str, x)))),
                ),
            )
            .reset_index()
        )
        for r in g.to_dict("records"):
            rows[str(r["facility_id"])] = r

    # Read from database
    with db() as c:
        for r in c.execute("SELECT * FROM hospitals ORDER BY facility_name").fetchall():
            d = dict(r)
            fid = str(d["facility_id"])
            existing = rows.get(fid, {})
            d.update(
                {
                    "equipment_count": existing.get("equipment_count", 0),
                    "equipment_types": existing.get("equipment_types", ""),
                }
            )
            rows[fid] = d

        # Get equipment counts from registry
        for r in c.execute("""
            SELECT facility_id, COUNT(*) AS equipment_count, 
                   GROUP_CONCAT(DISTINCT equipment_type) AS equipment_types 
            FROM equipment_registry 
            GROUP BY facility_id
        """).fetchall():
            fid = str(r["facility_id"])
            d = rows.setdefault(fid, {"facility_id": fid})
            d["equipment_count"] = int(r["equipment_count"] or 0)
            if r["equipment_types"]:
                d["equipment_types"] = r["equipment_types"]

    return list(rows.values())


def equipment():
    """Get equipment from database and CSV"""
    rows = {}

    # Read from CSV
    e = read_csv("equipment_master.csv")
    if not e.empty:
        for r in e.to_dict("records"):
            rows[(str(r.get("equipment_id")), str(r.get("facility_id")))] = r

    # Read from database
    with db() as c:
        for r in c.execute("SELECT * FROM equipment_registry").fetchall():
            d = dict(r)
            key = (str(d["equipment_id"]), str(d["facility_id"]))
            base = rows.get(key, {})
            base.update(d)
            rows[key] = base

    return list(rows.values())


def telemetry(equipment_id=None, facility_id=None, limit=100):
    """Get telemetry data from CSV"""
    d = read_csv("sensor_telemetry.csv")
    if d.empty:
        return []
    if equipment_id is not None:
        d = d[d["equipment_id"].astype(str) == str(equipment_id)]
    if facility_id is not None and "facility_id" in d.columns:
        d = d[d["facility_id"].astype(str) == str(facility_id)]
    if "timestamp" in d.columns:
        d = d.sort_values("timestamp", ascending=False)
    return d.head(limit).to_dict("records")


def maintenance(equipment_id=None, facility_id=None, limit=200):
    """Get maintenance history from CSV"""
    d = read_csv("maintenance_history.csv")
    if d.empty:
        return []
    if equipment_id is not None:
        d = d[d["equipment_id"].astype(str) == str(equipment_id)]
    if facility_id is not None and "facility_id" in d.columns:
        d = d[d["facility_id"].astype(str) == str(facility_id)]
    if "maintenance_date" in d.columns:
        d = d.sort_values("maintenance_date", ascending=False)
    return d.head(limit).to_dict("records")


def failures(equipment_id=None, facility_id=None, limit=200):
    """Get failure events from CSV"""
    d = read_csv("failure_events.csv")
    if d.empty:
        return []
    if equipment_id is not None:
        d = d[d["equipment_id"].astype(str) == str(equipment_id)]
    if facility_id is not None and "facility_id" in d.columns:
        d = d[d["facility_id"].astype(str) == str(facility_id)]
    if "failure_timestamp" in d.columns:
        d = d.sort_values("failure_timestamp", ascending=False)
    return d.head(limit).to_dict("records")


def usage(equipment_id=None, facility_id=None, limit=200):
    """Get usage history from CSV"""
    d = read_csv("usage_reporting_log.csv")
    if d.empty:
        return []
    if equipment_id is not None:
        d = d[d["equipment_id"].astype(str) == str(equipment_id)]
    if facility_id is not None and "facility_id" in d.columns:
        d = d[d["facility_id"].astype(str) == str(facility_id)]
    if "week_start" in d.columns:
        d = d.sort_values("week_start", ascending=False)
    return d.head(limit).to_dict("records")


def alerts(equipment_id=None, facility_id=None, status=None, severity=None, limit=100):
    """Get alerts from database"""
    with db() as c:
        query = "SELECT * FROM alerts WHERE 1=1"
        params = []

        if equipment_id:
            query += " AND equipment_id=?"
            params.append(equipment_id)
        if facility_id:
            query += " AND facility_id=?"
            params.append(facility_id)
        if status:
            query += " AND status=?"
            params.append(status)
        if severity:
            query += " AND severity=?"
            params.append(severity)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = [dict(r) for r in c.execute(query, params).fetchall()]

    return rows


def scope_filter(rows, user, facility_key="facility_id"):
    """Filter rows by user's scope"""
    if rows is None:
        return []
    if str(user.get("scope_type", "")).lower() == "national":
        return rows
    sid = str(user.get("scope_id") or "")
    return [r for r in rows if str(r.get(facility_key, "")) == sid]


# --- Data Sync Functions ---
def sync_equipment_from_csv():
    """Sync equipment from CSV to database"""
    logger.info("Syncing equipment from CSV to database...")

    df = read_csv("equipment_master.csv", refresh=True)
    if df.empty:
        logger.warning("No equipment data found in CSV")
        return {"added": 0, "updated": 0, "errors": 0}

    added = 0
    updated = 0
    errors = 0
    now = datetime.now(timezone.utc).isoformat()

    with db() as c:
        for _, row in df.iterrows():
            try:
                equipment_id = str(row.get("equipment_id", ""))
                facility_id = str(row.get("facility_id", ""))

                if not equipment_id or not facility_id:
                    continue

                existing = c.execute(
                    "SELECT * FROM equipment_registry WHERE equipment_id=? AND facility_id=?",
                    (equipment_id, facility_id),
                ).fetchone()

                if existing:
                    c.execute(
                        """
                        UPDATE equipment_registry 
                        SET equipment_type=?, manufacturer=?, model=?, 
                            serial_number=?, status=?, updated_at=?
                        WHERE equipment_id=? AND facility_id=?
                    """,
                        (
                            str(row.get("equipment_type", "Unknown")),
                            str(row.get("manufacturer", "")),
                            str(row.get("model", "")),
                            str(row.get("serial_number", "")),
                            str(row.get("status", "OPERATIONAL")),
                            now,
                            equipment_id,
                            facility_id,
                        ),
                    )
                    updated += 1
                else:
                    c.execute(
                        """
                        INSERT INTO equipment_registry 
                        (equipment_id, facility_id, equipment_type, manufacturer, 
                         model, serial_number, status, installation_date, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            equipment_id,
                            facility_id,
                            str(row.get("equipment_type", "Unknown")),
                            str(row.get("manufacturer", "")),
                            str(row.get("model", "")),
                            str(row.get("serial_number", "")),
                            str(row.get("status", "OPERATIONAL")),
                            str(row.get("installation_date", now)),
                            now,
                            now,
                        ),
                    )
                    added += 1
            except Exception as e:
                logger.error(f"Error syncing equipment {row.get('equipment_id')}: {e}")
                errors += 1

    logger.info(
        f"Equipment sync complete: {added} added, {updated} updated, {errors} errors"
    )
    return {"added": added, "updated": updated, "errors": errors}


def sync_telemetry_from_csv():
    """Sync telemetry data from CSV to database"""
    logger.info("Syncing telemetry from CSV to database...")

    df = read_csv("sensor_telemetry.csv", refresh=True)
    if df.empty:
        logger.warning("No telemetry data found in CSV")
        return {"added": 0, "errors": 0}

    added = 0
    errors = 0

    with db() as c:
        for _, row in df.iterrows():
            try:
                equipment_id = str(row.get("equipment_id", ""))
                facility_id = str(row.get("facility_id", ""))

                if not equipment_id or not facility_id:
                    continue

                # Check if equipment exists
                exists = c.execute(
                    "SELECT 1 FROM equipment_registry WHERE equipment_id=? AND facility_id=?",
                    (equipment_id, facility_id),
                ).fetchone()

                if not exists:
                    c.execute(
                        """
                        INSERT INTO equipment_registry 
                        (equipment_id, facility_id, equipment_type, status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            equipment_id,
                            facility_id,
                            str(row.get("equipment_type", "Unknown")),
                            "OPERATIONAL",
                            datetime.now(timezone.utc).isoformat(),
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )

                added += 1
            except Exception as e:
                logger.error(f"Error syncing telemetry: {e}")
                errors += 1

    logger.info(f"Telemetry sync complete: {added} records processed, {errors} errors")
    return {"added": added, "errors": errors}


def get_equipment_telemetry(equipment_id, facility_id=None, limit=100, days=None):
    """Get telemetry data for equipment from CSV"""
    df = read_csv("sensor_telemetry.csv")
    if df.empty:
        return []

    df = df[df["equipment_id"].astype(str) == str(equipment_id)]

    if facility_id and "facility_id" in df.columns:
        df = df[df["facility_id"].astype(str) == str(facility_id)]

    if days and "timestamp" in df.columns:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        df = df[df["timestamp"] > cutoff]

    if "timestamp" in df.columns:
        df = df.sort_values("timestamp", ascending=False)

    return df.head(limit).to_dict("records")


def get_equipment_for_prediction(equipment_id):
    """Get equipment data and latest telemetry for prediction"""
    eq_data = None
    with db() as c:
        row = c.execute(
            "SELECT * FROM equipment_registry WHERE equipment_id=?", (equipment_id,)
        ).fetchone()
        if row:
            eq_data = dict(row)

    if not eq_data:
        return None

    telemetry_data = get_equipment_telemetry(equipment_id, limit=1)

    return {
        "equipment": eq_data,
        "latest_telemetry": telemetry_data[0] if telemetry_data else None,
        "has_telemetry": len(telemetry_data) > 0,
    }


def get_all_equipment_for_prediction():
    """Get all equipment with their latest telemetry"""
    result = []

    with db() as c:
        equipment_list = c.execute("SELECT * FROM equipment_registry").fetchall()

        for eq in equipment_list:
            eq_dict = dict(eq)
            telemetry_data = get_equipment_telemetry(eq_dict["equipment_id"], limit=1)
            result.append(
                {
                    "equipment": eq_dict,
                    "latest_telemetry": telemetry_data[0] if telemetry_data else None,
                    "has_telemetry": len(telemetry_data) > 0,
                }
            )

    return result


# ============================================
# CSV SYNC FUNCTIONS
# ============================================


def sync_equipment_to_csv(equipment_record: dict):
    """Sync a single equipment record to the master CSV"""
    import pandas as pd
    from app.core.paths import DATA_DIR

    csv_path = DATA_DIR / "equipment_master.csv"

    # Get facility details
    facility_name = ""
    county = ""
    keph_level = ""

    with db() as c:
        facility = c.execute(
            "SELECT facility_name, county, keph_level FROM hospitals WHERE facility_id=?",
            (equipment_record.get("facility_id"),),
        ).fetchone()
        if facility:
            facility_dict = dict(facility)
            facility_name = facility_dict.get("facility_name", "")
            county = facility_dict.get("county", "")
            keph_level = facility_dict.get("keph_level", "")

    # Prepare record
    new_record = {
        "equipment_id": equipment_record.get("equipment_id"),
        "facility_id": equipment_record.get("facility_id"),
        "facility": facility_name,
        "equipment_type": equipment_record.get("equipment_type", "Unknown"),
        "manufacturer": equipment_record.get("manufacturer", ""),
        "model": equipment_record.get("model", ""),
        "serial_number": equipment_record.get("serial_number", ""),
        "status": equipment_record.get("status", "OPERATIONAL"),
        "installation_date": equipment_record.get("installation_date", ""),
        "county": county,
        "keph_level": keph_level,
    }

    # Read existing CSV or create new
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        # Check if equipment already exists
        mask = (df["equipment_id"] == new_record["equipment_id"]) & (
            df["facility_id"] == new_record["facility_id"]
        )
        if mask.any():
            # Update existing row
            for key, value in new_record.items():
                if key in df.columns:
                    df.loc[mask, key] = value
        else:
            # Append new row
            df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    else:
        # Create new dataframe
        df = pd.DataFrame([new_record])

    # Save back to CSV
    df.to_csv(csv_path, index=False)
    logger.info(f"Equipment {new_record['equipment_id']} synced to CSV")
    return True


def sync_all_equipment_to_csv():
    """Sync all equipment from database to CSV"""
    import pandas as pd
    from app.core.paths import DATA_DIR

    csv_path = DATA_DIR / "equipment_master.csv"

    with db() as c:
        equipment_list = c.execute("""
            SELECT e.*, h.facility_name, h.county, h.keph_level
            FROM equipment_registry e
            LEFT JOIN hospitals h ON e.facility_id = h.facility_id
        """).fetchall()

        records = []
        for eq in equipment_list:
            eq_dict = dict(eq)
            records.append(
                {
                    "equipment_id": eq_dict.get("equipment_id", ""),
                    "facility_id": eq_dict.get("facility_id", ""),
                    "facility": eq_dict.get("facility_name", ""),
                    "equipment_type": eq_dict.get("equipment_type", "Unknown"),
                    "manufacturer": eq_dict.get("manufacturer", ""),
                    "model": eq_dict.get("model", ""),
                    "serial_number": eq_dict.get("serial_number", ""),
                    "status": eq_dict.get("status", "OPERATIONAL"),
                    "installation_date": eq_dict.get("installation_date", ""),
                    "county": eq_dict.get("county", ""),
                    "keph_level": eq_dict.get("keph_level", ""),
                }
            )

        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False)
        logger.info(f"Synced {len(records)} equipment records to CSV")
        return {"synced": len(records)}


def sync_telemetry_to_csv(telemetry_record: dict):
    """Sync a telemetry record to the sensor telemetry CSV"""
    import pandas as pd
    from app.core.paths import DATA_DIR
    from datetime import datetime, timezone

    csv_path = DATA_DIR / "sensor_telemetry.csv"

    # Prepare record
    new_record = {
        "timestamp": telemetry_record.get(
            "timestamp", datetime.now(timezone.utc).isoformat()
        ),
        "equipment_id": telemetry_record.get("equipment_id"),
        "facility_id": telemetry_record.get("facility_id"),
        "equipment_type": telemetry_record.get("equipment_type", "Unknown"),
        "temperature": telemetry_record.get("temperature", 0),
        "vibration": telemetry_record.get("vibration", 0),
        "pressure": telemetry_record.get("pressure", 0),
        "humidity": telemetry_record.get("humidity", 0),
        "power_consumption": telemetry_record.get("power_consumption", 0),
        "risk_score": telemetry_record.get("risk_score", 0),
        "operational_status": telemetry_record.get("operational_status", "NORMAL"),
        "anomaly": telemetry_record.get("anomaly", False),
    }

    # Read existing CSV or create new
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        # Keep only last 10000 records per equipment
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        df = df.groupby("equipment_id").tail(10000)
    else:
        df = pd.DataFrame([new_record])

    # Save back to CSV
    df.to_csv(csv_path, index=False)
    logger.debug(f"Telemetry record synced to CSV for {new_record['equipment_id']}")
    return True


def sync_telemetry_batch_to_csv(telemetry_records: list):
    """Sync multiple telemetry records to CSV"""
    import pandas as pd
    from app.core.paths import DATA_DIR

    csv_path = DATA_DIR / "sensor_telemetry.csv"

    if not telemetry_records:
        return {"synced": 0}

    df_new = pd.DataFrame(telemetry_records)

    if csv_path.exists():
        df_existing = pd.read_csv(csv_path)
        df = pd.concat([df_existing, df_new], ignore_index=True)
        # Keep only last 10000 records per equipment
        df = df.groupby("equipment_id").tail(10000)
    else:
        df = df_new

    df.to_csv(csv_path, index=False)
    logger.info(f"Synced {len(telemetry_records)} telemetry records to CSV")
    return {"synced": len(telemetry_records)}
