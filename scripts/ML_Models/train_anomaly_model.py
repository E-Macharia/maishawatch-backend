import joblib
import pandas as pd

from sklearn.ensemble import IsolationForest


df = pd.read_csv(

    "data/sensor_telemetry.csv"
)


features = [

    "temperature",

    "vibration",

    "pressure",

    "flow_rate",

    "power_consumption"
]


X = df[features]


model = IsolationForest(

    contamination=0.05,

    random_state=42
)


model.fit(X)


joblib.dump(

    model,

    "models/anomaly_model.pkl"
)