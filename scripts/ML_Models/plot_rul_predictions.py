import joblib
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split

df = pd.read_csv(
    "data/sensor_telemetry.csv"
)

X = df.drop(
    columns=[
        "timestamp",
        "equipment_id",
        "failure",
        "rul_hours"
    ],
    errors="ignore"
)

y = df["rul_hours"]

categorical_columns = list(
    X.select_dtypes(
        include=["object", "string"]
    ).columns
)

X = pd.get_dummies(
    X,
    columns=categorical_columns,
    drop_first=True
)

X = X.fillna(0)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)

model = joblib.load(
    "models/rul_model.pkl"
)

predictions = model.predict(
    X_test
)

plt.figure(
    figsize=(10, 8)
)

plt.scatter(
    y_test,
    predictions,
    alpha=0.2
)

plt.xlabel(
    "Actual RUL (hours)"
)

plt.ylabel(
    "Predicted RUL (hours)"
)

plt.title(
    "Remaining Useful Life Prediction"
)

plt.plot(
    [y_test.min(), y_test.max()],
    [y_test.min(), y_test.max()]
)

plt.savefig(
    "models/rul_prediction_plot.png"
)

plt.show()