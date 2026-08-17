"""
Layer 1 ingestion: NASA C-MAPSS turbofan degradation dataset (FD001).

Used to validate the breakdown-risk prediction *method* (sensor readings -> degradation
-> remaining-useful-life), not joined to real facility/equipment data -- this is a
methodology validation dataset, kept separate from the Kenya facility/equipment pipeline.

Source: NASA Prognostics Center of Excellence, Saxena & Goebel (2008).
"""
from pathlib import Path
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "cmapss"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Official column layout: unit number, cycle, 3 operational settings, 21 sensor measurements.
COLUMNS = (
    ["unit_number", "cycle", "op_setting_1", "op_setting_2", "op_setting_3"]
    + [f"sensor_{i}" for i in range(1, 22)]
)


def load_subset(subset: str = "FD001") -> dict[str, pd.DataFrame]:
    """
    Load one C-MAPSS subset (FD001-FD004).

    Returns a dict with:
      - 'train': full run-to-failure trajectories (used for training/validating the
        degradation model)
      - 'test': truncated trajectories (used for RUL prediction evaluation)
      - 'rul': true remaining-useful-life for each unit in the test set, in unit order
    """
    train_path = RAW_DIR / f"train_{subset}.txt"
    test_path = RAW_DIR / f"test_{subset}.txt"
    rul_path = RAW_DIR / f"RUL_{subset}.txt"

    for p in (train_path, test_path, rul_path):
        if not p.exists():
            raise FileNotFoundError(f"Expected C-MAPSS file not found: {p}")

    # Files are whitespace-delimited with trailing whitespace producing extra empty
    # columns if you're not careful -- delim_whitespace handles this correctly.
    train = pd.read_csv(train_path, sep=r"\s+", header=None, names=COLUMNS)
    test = pd.read_csv(test_path, sep=r"\s+", header=None, names=COLUMNS)
    rul = pd.read_csv(rul_path, sep=r"\s+", header=None, names=["RUL"])
    rul["unit_number"] = rul.index + 1  # RUL file is in unit-number order, 1-indexed

    # Add RUL (remaining useful life) as a training label: for each unit, RUL at a given
    # cycle = (max cycle for that unit) - (current cycle). This is the standard C-MAPSS
    # labeling approach for the training set (the test set's RUL comes from RUL_FD001.txt).
    train["max_cycle"] = train.groupby("unit_number")["cycle"].transform("max")
    train["RUL"] = train["max_cycle"] - train["cycle"]
    train = train.drop(columns="max_cycle")

    return {"train": train, "test": test, "rul": rul}


def main():
    data = load_subset("FD001")
    data["train"].to_csv(OUT_DIR / "cmapss_fd001_train.csv", index=False)
    data["test"].to_csv(OUT_DIR / "cmapss_fd001_test.csv", index=False)
    data["rul"].to_csv(OUT_DIR / "cmapss_fd001_rul.csv", index=False)

    print(f"Train: {data['train'].shape[0]:,} rows, {data['train'].unit_number.nunique()} units")
    print(f"Test:  {data['test'].shape[0]:,} rows, {data['test'].unit_number.nunique()} units")
    print(f"RUL:   {data['rul'].shape[0]:,} units")
    print(f"Saved to: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
