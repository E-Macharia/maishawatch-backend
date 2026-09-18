import pandas as pd
import joblib

df = pd.read_csv(
    "data/ml/failure_prediction_24h.csv"
)

X = df.drop(
    columns=[
        "failure_next_24h",
        "timestamp",
        "equipment_id"
    ],
    errors="ignore"
)

categorical = X.select_dtypes(
    include=["object", "string", "category"]
).columns

X = pd.get_dummies(
    X,
    columns=categorical
)

joblib.dump(
    X.columns.tolist(),
    "models/failure_feature_names.pkl"
)

print(
    f"Saved {len(X.columns)} features"
)