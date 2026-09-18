import os
import joblib
import pandas as pd

from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
)

MODEL_DIR = "models"

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)


HORIZONS = [
    "24h",
    "72h",
    "168h"
]


for horizon in HORIZONS:

    print("\n")
    print("=" * 60)
    print(f"TRAINING FAILURE MODEL: {horizon}")
    print("=" * 60)

    # ---------------------------------------------------------
    # LOAD THE CORRECT DATASET FOR THIS HORIZON
    # ---------------------------------------------------------

    data_path = (
        f"data/ml/failure_prediction_{horizon}.csv"
    )

    target = (
        f"failure_next_{horizon}"
    )

    print(
        f"Loading: {data_path}"
    )

    df = pd.read_csv(
        data_path
    )

    print(
        "Dataset shape:",
        df.shape
    )

    print(
        "Target:",
        target
    )

    # ---------------------------------------------------------
    # CHECK TARGET EXISTS
    # ---------------------------------------------------------

    if target not in df.columns:

        raise ValueError(
            f"Target '{target}' not found in {data_path}"
        )

    print(
        "Failure distribution:"
    )

    print(
        df[target].value_counts()
    )

    # ---------------------------------------------------------
    # REMOVE NON-FEATURE COLUMNS
    # ---------------------------------------------------------

    DROP_COLUMNS = [
        "timestamp",
        "equipment_id",
        target
    ]

    X = df.drop(
        columns=DROP_COLUMNS,
        errors="ignore"
    )

    y = df[target]

    # ---------------------------------------------------------
    # CONVERT CATEGORICAL VARIABLES
    # ---------------------------------------------------------

    categorical_columns = list(
        X.select_dtypes(
            include=[
                "object",
                "string",
                "category"
            ]
        ).columns
    )

    print(
        "Categorical columns:",
        len(categorical_columns)
    )

    if categorical_columns:

        X = pd.get_dummies(
            X,
            columns=categorical_columns,
            dtype=float
        )

    # ---------------------------------------------------------
    # CLEAN NUMERIC DATA
    # ---------------------------------------------------------

    X = X.replace(
        [float("inf"), float("-inf")],
        0
    )

    X = X.fillna(
        0
    )

    # Make absolutely sure every feature is numeric
    X = X.astype(float)

    print(
        "Final feature count:",
        X.shape[1]
    )

    # ---------------------------------------------------------
    # TRAIN / TEST SPLIT
    # ---------------------------------------------------------

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y
    )

    # ---------------------------------------------------------
    # CREATE A NEW MODEL FOR THIS HORIZON
    # ---------------------------------------------------------

    model = XGBClassifier(

        n_estimators=500,

        max_depth=8,

        learning_rate=0.05,

        subsample=0.8,

        colsample_bytree=0.8,

        objective="binary:logistic",

        eval_metric="logloss",

        tree_method="hist",

        random_state=42,

        n_jobs=-1
    )

    # ---------------------------------------------------------
    # TRAIN
    # ---------------------------------------------------------

    print(
        f"\nTraining {horizon} model..."
    )

    model.fit(
        X_train,
        y_train
    )

    # ---------------------------------------------------------
    # EVALUATION
    # ---------------------------------------------------------

    predictions = model.predict(
        X_test
    )

    probabilities = model.predict_proba(
        X_test
    )[:, 1]

    print(
        f"\n{horizon} classification report:"
    )

    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0
        )
    )

    try:

        auc = roc_auc_score(
            y_test,
            probabilities
        )

        print(
            "ROC-AUC:",
            round(auc, 4)
        )

    except Exception:

        pass

    # ---------------------------------------------------------
    # SAVE MODEL
    # ---------------------------------------------------------

    model_path = (
        f"{MODEL_DIR}/failure_model_{horizon}.pkl"
    )

    joblib.dump(
        model,
        model_path
    )

    print(
        f"\nSaved: {model_path}"
    )

    print(
        "Features saved in model:",
        len(model.feature_names_in_)
    )

    print(
        "First 10 features:"
    )

    print(
        list(model.feature_names_in_[:10])
    )


print("\n")
print("=" * 60)
print("ALL FAILURE MODELS TRAINED")
print("=" * 60)