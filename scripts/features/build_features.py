"""
Week 2 — Feature engineering (Valentine, Data Engineer)

Builds one row per equipment_id in `equipment_features.csv`, combining:
  - Usage trend features (from sensor_telemetry.csv)
  - Maintenance interval features (from maintenance_history.csv)
  - Discrepancy features (from usage_reporting_log.csv)

Output is what Caleb's breakdown-risk model and discrepancy-flagging logic should train
against directly -- one row per equipment, model-ready. Labels (scenario_type,
scenario_rationale) are carried through from equipment_master.csv so this file can be used
for both supervised training and for tracing any prediction back to its cited real-world
rationale.
"""
from pathlib import Path
import numpy as np
import pandas as pd

# In your repo this becomes: Path(__file__).resolve().parents[2] / "data"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
OUT_DIR = DATA_DIR / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RECENT_WINDOW_DAYS = 14   # "recent" window for trend/short-term features
LONG_WINDOW_DAYS = 90     # full observation window (matches generator's DAYS=90)
DISCREPANCY_FLAG_THRESHOLD = 0.15  # a week counts as "flagged" if discrepancy_pct exceeds this


def load_inputs():
    eq = pd.read_csv(DATA_DIR / "equipment_master.csv")
    tele = pd.read_csv(DATA_DIR / "sensor_telemetry.csv", parse_dates=["timestamp"])
    maint = pd.read_csv(DATA_DIR / "maintenance_history.csv", parse_dates=["maintenance_date"])
    usage = pd.read_csv(DATA_DIR / "usage_reporting_log.csv", parse_dates=["week_start"])
    return eq, tele, maint, usage


# ---------------------------------------------------------------------------
# Usage trend features (from sensor_telemetry.csv)
# ---------------------------------------------------------------------------
def build_usage_trend_features(tele: pd.DataFrame) -> pd.DataFrame:
    tele = tele.sort_values(["equipment_id", "timestamp"])
    max_ts = tele["timestamp"].max()
    recent_cutoff = max_ts - pd.Timedelta(days=RECENT_WINDOW_DAYS)

    overall = tele.groupby("equipment_id").agg(
        avg_utilization_90d=("utilization_rate", "mean"),
        avg_risk_score_90d=("risk_score", "mean"),
        max_risk_score_90d=("risk_score", "max"),
        avg_degradation_index_90d=("degradation_index", "mean"),
        avg_temperature_anomaly_90d=("temperature_anomaly", "mean"),
        avg_vibration_anomaly_90d=("vibration_anomaly", "mean"),
        pct_hours_critical_90d=("condition_status", lambda s: (s == "Critical").mean()),
        pct_hours_warning_or_worse_90d=("condition_status", lambda s: s.isin(["Critical", "High"]).mean()),
        total_failures_90d=("failure", "sum"),
        latest_risk_score=("risk_score", "last"),
        latest_degradation_index=("degradation_index", "last"),
        latest_operating_hours=("operating_hours", "last"),
    ).reset_index()

    recent = (tele[tele["timestamp"] >= recent_cutoff]
              .groupby("equipment_id")
              .agg(avg_utilization_recent=("utilization_rate", "mean"),
                   avg_risk_score_recent=("risk_score", "mean"))
              .reset_index())

    trend = overall.merge(recent, on="equipment_id", how="left")
    # Simple trend signal: recent risk vs full-window average risk. Positive means
    # risk is climbing lately relative to the whole observation window.
    trend["risk_score_trend"] = trend["avg_risk_score_recent"] - trend["avg_risk_score_90d"]
    trend["utilization_trend"] = trend["avg_utilization_recent"] - trend["avg_utilization_90d"]

    return trend


# ---------------------------------------------------------------------------
# Maintenance interval features (from maintenance_history.csv)
# ---------------------------------------------------------------------------
def build_maintenance_features(maint: pd.DataFrame, eq: pd.DataFrame) -> pd.DataFrame:
    maint = maint.sort_values(["equipment_id", "maintenance_date"])

    counts = maint.groupby("equipment_id").agg(
        maintenance_event_count=("maintenance_id", "count"),
        avg_downtime_hours=("downtime_hours", "mean"),
        total_parts_cost=("parts_cost", "sum"),
    ).reset_index()

    # Average gap between consecutive maintenance events, per equipment
    def avg_gap(group):
        dates = group["maintenance_date"].sort_values()
        if len(dates) < 2:
            return np.nan
        return dates.diff().dt.days.mean()

    gaps = (maint.groupby("equipment_id")
                 .apply(avg_gap, include_groups=False)
                 .reset_index(name="avg_days_between_maintenance"))

    feats = counts.merge(gaps, on="equipment_id", how="outer")

    # Equipment with zero maintenance events won't appear in `maint` at all --
    # left-join against the full equipment list and fill zeros/NaN explicitly,
    # rather than silently dropping them (a zero-maintenance record is itself
    # a meaningful signal for the neglect pattern).
    feats = eq[["equipment_id", "maintenance_interval_days", "last_maintenance_date"]].merge(
        feats, on="equipment_id", how="left"
    )
    feats["maintenance_event_count"] = feats["maintenance_event_count"].fillna(0).astype(int)

    latest_date = pd.to_datetime(feats["last_maintenance_date"])
    today = pd.Timestamp("2026-08-13")  # pipeline reference date; adjust if re-run later
    feats["days_since_last_maintenance"] = (today - latest_date).dt.days
    feats["maintenance_overdue"] = (
        feats["days_since_last_maintenance"] >= feats["maintenance_interval_days"]
    )

    return feats.drop(columns=["last_maintenance_date"])


# ---------------------------------------------------------------------------
# Discrepancy features (from usage_reporting_log.csv)
# ---------------------------------------------------------------------------
def build_discrepancy_features(usage: pd.DataFrame, eq: pd.DataFrame) -> pd.DataFrame:
    usage = usage.sort_values(["equipment_id", "week_start"])

    agg = usage.groupby("equipment_id").agg(
        avg_discrepancy_pct=("discrepancy_pct", "mean"),
        max_discrepancy_pct=("discrepancy_pct", "max"),
        std_discrepancy_pct=("discrepancy_pct", "std"),
        weeks_observed=("week_start", "count"),
    ).reset_index()

    flagged_weeks = (usage.assign(is_flagged=usage["discrepancy_pct"] > DISCREPANCY_FLAG_THRESHOLD)
                           .groupby("equipment_id")["is_flagged"]
                           .sum()
                           .reset_index(name="weeks_flagged"))

    feats = agg.merge(flagged_weeks, on="equipment_id", how="left")
    feats["pct_weeks_flagged"] = (feats["weeks_flagged"] / feats["weeks_observed"]).fillna(0)

    # Trend: is the discrepancy widening or narrowing over the observation window?
    def discrepancy_trend(group):
        if len(group) < 2:
            return 0.0
        x = np.arange(len(group))
        y = group["discrepancy_pct"].values
        return float(np.polyfit(x, y, 1)[0])  # slope

    trend = (usage.groupby("equipment_id")
                  .apply(discrepancy_trend, include_groups=False)
                  .reset_index(name="discrepancy_pct_trend"))

    feats = feats.merge(trend, on="equipment_id", how="left")

    # Equipment with zero usage-log weeks (shouldn't happen given generator, but guard
    # against it) get explicit zeros, not silent drops.
    feats = eq[["equipment_id"]].merge(feats, on="equipment_id", how="left")
    for col in ["avg_discrepancy_pct", "max_discrepancy_pct", "std_discrepancy_pct",
                "weeks_observed", "weeks_flagged", "pct_weeks_flagged", "discrepancy_pct_trend"]:
        feats[col] = feats[col].fillna(0)

    return feats


# ---------------------------------------------------------------------------
# Combine
# ---------------------------------------------------------------------------
def main():
    eq, tele, maint, usage = load_inputs()

    usage_trend = build_usage_trend_features(tele)
    maintenance = build_maintenance_features(maint, eq)
    discrepancy = build_discrepancy_features(usage, eq)

    features = (eq[["equipment_id", "equipment_type", "facility_id", "facility", "county",
                     "keph_level", "criticality", "scenario_type", "scenario_rationale"]]
                .merge(usage_trend, on="equipment_id", how="left")
                .merge(maintenance, on="equipment_id", how="left")
                .merge(discrepancy, on="equipment_id", how="left"))

    # Convenience binary labels for model training, derived from scenario_type
    # (kept alongside scenario_type/scenario_rationale, not replacing them)
    features["label_maintenance_neglect"] = features["scenario_type"].str.contains("MaintenanceNeglect")
    features["label_usage_discrepancy"] = features["scenario_type"].str.contains("UsageDiscrepancy")
    features["label_any_failure"] = features["total_failures_90d"] > 0

    features.to_csv(OUT_DIR / "equipment_features.csv", index=False)

    print(f"Equipment rows: {len(features):,}")
    print(f"Feature columns: {features.shape[1]}")
    print(f"label_maintenance_neglect=True: {features.label_maintenance_neglect.sum():,}")
    print(f"label_usage_discrepancy=True: {features.label_usage_discrepancy.sum():,}")
    print(f"label_any_failure=True: {features.label_any_failure.sum():,}")
    print(f"Saved to: {(OUT_DIR / 'equipment_features.csv').resolve()}")


if __name__ == "__main__":
    main()
