import os
import numpy as np
import pandas as pd

os.makedirs("data/ml", exist_ok=True)

print("\nLoading datasets...")

telemetry = pd.read_csv("data/sensor_telemetry.csv")
equipment = pd.read_csv("data/processed/equipment_features.csv")

telemetry["timestamp"] = pd.to_datetime(telemetry["timestamp"])

telemetry = telemetry.sort_values(
    ["equipment_id", "timestamp"]
)

print("Telemetry:", telemetry.shape)
print("Equipment:", equipment.shape)

print("\nMerging datasets...")

drop_columns = [
    "equipment_type",
    "facility_id",
    "facility",
    "county"
]

equipment_merge = equipment.drop(
    columns=[
        c for c in drop_columns
        if c in equipment.columns
    ],
    errors="ignore"
)

df = telemetry.merge(
    equipment_merge,
    on="equipment_id",
    how="left"
)

print("Merged:", df.shape)

print("\nCreating time features...")

df["hour"] = df["timestamp"].dt.hour
df["day_of_week"] = df["timestamp"].dt.dayofweek
df["day_of_month"] = df["timestamp"].dt.day
df["month"] = df["timestamp"].dt.month
df["week_of_year"] = df["timestamp"].dt.isocalendar().week.astype(int)
df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

sensor_columns = [
    "temperature",
    "vibration",
    "pressure",
    "flow_rate",
    "power_consumption",
    "humidity",
    "utilization_rate",
    "risk_score",
    "degradation_index",
    "rul_hours"
]

print("\nCreating rolling features...")

for sensor in sensor_columns:

    if sensor not in df.columns:
        continue

    print(sensor)

    grouped = df.groupby("equipment_id")[sensor]

    df[f"{sensor}_mean_6h"] = (
        grouped.transform(
            lambda x: (
                x.rolling(
                    6,
                    min_periods=1
                ).mean()
            )
        )
    )

    df[f"{sensor}_std_6h"] = (
        grouped.transform(
            lambda x: (
                x.rolling(
                    6,
                    min_periods=1
                ).std()
            )
        )
    )

    df[f"{sensor}_mean_24h"] = (
        grouped.transform(
            lambda x: (
                x.rolling(
                    24,
                    min_periods=1
                ).mean()
            )
        )
    )

    df[f"{sensor}_std_24h"] = (
        grouped.transform(
            lambda x: (
                x.rolling(
                    24,
                    min_periods=1
                ).std()
            )
        )
    )

    df[f"{sensor}_diff_1h"] = grouped.diff()

print("\nCreating future failure labels...")

for target, window in {
    "failure_next_24h": 24,
    "failure_next_72h": 72,
    "failure_next_168h": 168,
}.items():
    df[target] = (
        df.groupby("equipment_id")["failure"]
        .transform(
            lambda x: x.shift(-1).rolling(window, min_periods=1).max()
        )
    )

targets = [
    "failure_next_24h",
    "failure_next_72h",
    "failure_next_168h",
]

for target in targets:
    df[target] = df[target].fillna(0).astype(int)

df = df.drop(columns=["failure"], errors="ignore")
df = df.fillna(0)

dataset_map = {
    "failure_next_24h": "data/ml/failure_prediction_24h.csv",
    "failure_next_72h": "data/ml/failure_prediction_72h.csv",
    "failure_next_168h": "data/ml/failure_prediction_168h.csv",
}

for target, output_file in dataset_map.items():
    dataset = df.copy()

    other_targets = [
        column for column in targets if column != target
    ]

    dataset = dataset.drop(columns=other_targets, errors="ignore")
    dataset.to_csv(output_file, index=False)

    print(f"\n{output_file}")
    print(f"Shape: {dataset.shape}")
    print(f"Positive rate: {dataset[target].mean():.4f}")

print("\nDatasets created successfully.")