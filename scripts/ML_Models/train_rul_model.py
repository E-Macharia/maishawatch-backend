import os
import joblib
import pandas as pd

from xgboost import XGBRegressor

from sklearn.model_selection import train_test_split

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

MODEL_DIR = "models"

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)

print("\nLoading telemetry dataset...")

df = pd.read_csv(
    "data/sensor_telemetry.csv"
)

print("Dataset shape:", df.shape)

df["timestamp"] = pd.to_datetime(
    df["timestamp"]
)

TARGET = "rul_hours"

DROP_COLUMNS = [
    "timestamp",
    "equipment_id",
    "failure",
    "rul_hours"
]

FEATURES = df.drop(
    columns=DROP_COLUMNS,
    errors="ignore"
)

TARGET_VALUES = df[TARGET]

categorical_columns = list(
    FEATURES.select_dtypes(
        include=["object", "string"]
    ).columns
)

print(
    "\nCategorical columns:",
    len(categorical_columns)
)

if categorical_columns:

    FEATURES = pd.get_dummies(
        FEATURES,
        columns=categorical_columns,
        drop_first=True
    )

    FEATURES = FEATURES.fillna(0)

    print(
        "Feature count:",
        FEATURES.shape[1]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        FEATURES,
        TARGET_VALUES,
        test_size=0.20,
        random_state=42
    )

    print("\nTraining XGBoost RUL model...")

    model = XGBRegressor(
        n_estimators=300,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        random_state=42,
        n_jobs=-1
    )

    model.fit(
        X_train,
        y_train
    )

    print("\nEvaluating model...")

    predictions = model.predict(
        X_test
    )

    mae = mean_absolute_error(
        y_test,
        predictions
    )

    mse = mean_squared_error(
        y_test,
        predictions
    )

    rmse = mse ** 0.5

    r2 = r2_score(
        y_test,
        predictions
    )

    print("\nResults")

    print("MAE:", round(mae, 2))
    print("RMSE:", round(rmse, 2))
    print("R²:", round(r2, 4))

    joblib.dump(
        model,
        f"{MODEL_DIR}/rul_model.pkl"
    )

    joblib.dump(
        FEATURES.columns.tolist(),
        f"{MODEL_DIR}/rul_features.pkl"
    )

    print("\nModel saved.")

    print(
        "models/rul_model.pkl"
    )