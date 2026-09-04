"""
Layer 1 ingestion: Kenya health facility master table.

Primary source: KMHFR-derived extract (openAFRICA mirror), 12,394 facilities.
Secondary/cross-check source: 2017 HDX KMHFR extract, 8,932 facilities.

Output: data/facility_master.csv
  - one row per facility, stable facility_id
  - all facility levels kept (per team decision)
  - equipment-eligibility flags added as separate boolean columns, so downstream
    joins can filter by equipment type without losing facilities from the master
"""
from pathlib import Path
import pandas as pd
import numpy as np

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "facility_census"
OUT_DIR = Path(__file__).resolve().parents[2] / "reference"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRIMARY_FILE = RAW_DIR / "cfafrica-_-data-team-_-outbreak-_-covid19-_-data-_-openafrica-uploads-_-kenya-hospital-ke.csv"
SECONDARY_FILE = RAW_DIR / "kenya-health-facilities-2017_08_02.xlsx"


def load_primary():
    df = pd.read_csv(PRIMARY_FILE)
    df["source"] = "kmhfr_openafrica_2020"
    return df


def load_secondary():
    df = pd.read_excel(SECONDARY_FILE)
    df["source"] = "kmhfr_hdx_2017"
    return df


def clean_county(s):
    if pd.isna(s):
        return s
    return str(s).strip().title()


def keph_level_numeric(s):
    if pd.isna(s):
        return np.nan
    s = str(s).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else np.nan


def build_facility_master():
    primary = load_primary()
    secondary = load_secondary()

    # Standardize primary (richer schema -- treat as base)
    primary = primary.rename(columns={
        "Code": "facility_code",
        "Name": "facility_name",
        "Officialname": "official_name",
        "Keph level": "keph_level",
        "Facility type": "facility_type",
        "Facility_type_category": "facility_type_category",
        "Owner": "owner",
        "Owner type": "owner_type",
        "Regulatory body": "regulatory_body",
        "Beds": "beds",
        "Cots": "cots",
        "Beds and Cots": "beds_and_cots",
        "County": "county",
        "Constituency": "constituency",
        "Sub county": "sub_county",
        "Ward": "ward",
        "Operation status": "operation_status",
        "Open_whole_day": "open_whole_day",
        "Open_public_holidays": "open_public_holidays",
        "Open_weekends": "open_weekends",
        "Open_late_night": "open_late_night",
        "Service_names": "service_names",
    })

    keep_cols = [
        "facility_code", "facility_name", "official_name", "keph_level",
        "facility_type", "facility_type_category", "owner", "owner_type",
        "regulatory_body", "beds", "cots", "beds_and_cots", "county",
        "constituency", "sub_county", "ward", "operation_status",
        "open_whole_day", "open_public_holidays", "open_weekends",
        "open_late_night", "service_names", "source",
    ]
    fm = primary[keep_cols].copy()

    # Basic cleaning
    fm["county"] = fm["county"].apply(clean_county)
    fm["facility_name"] = fm["facility_name"].astype(str).str.strip()
    fm["keph_level_numeric"] = fm["keph_level"].apply(keph_level_numeric)

    # Drop rows with no name or no county -- unusable as a join target
    before = len(fm)
    fm = fm[fm["facility_name"].notna() & (fm["facility_name"].str.len() > 0)]
    fm = fm[fm["county"].notna()]
    dropped = before - len(fm)

    # Deduplicate: same facility_code should be unique; if code is missing, fall back
    # to (facility_name, county, sub_county) as a composite key
    fm["facility_code"] = fm["facility_code"].astype("string")
    has_code = fm["facility_code"].notna()
    fm_coded = fm[has_code].drop_duplicates(subset=["facility_code"])
    fm_uncoded = fm[~has_code].drop_duplicates(subset=["facility_name", "county", "sub_county"])
    fm = pd.concat([fm_coded, fm_uncoded], ignore_index=True)

    # Stable facility_id: prefer real KMHFR code, else a generated surrogate key
    fm = fm.reset_index(drop=True)
    fm["facility_id"] = fm["facility_code"].where(
        fm["facility_code"].notna(),
        "GEN-" + fm.index.astype(str).str.zfill(6)
    )

    # ---- Equipment-eligibility flags (does NOT filter rows, just annotates) ----
    # Kenyan facility levels: 2=dispensary, 3=health centre, 4=sub-county hospital,
    # 5=county referral hospital, 6=national referral/teaching hospital.
    # Dialysis, ICU, and theatre-grade equipment (Anesthesia) realistically require
    # Level 4+; advanced imaging (MRI/CT) realistically requires Level 5+; X-Ray,
    # Ultrasound, and Patient Monitors are plausible from Level 3+.
    lvl = fm["keph_level_numeric"]
    fm["eligible_hemodialysis"] = lvl >= 4
    fm["eligible_icu_ventilator"] = lvl >= 4
    fm["eligible_anesthesia_theatre"] = lvl >= 4
    fm["eligible_mri_ct"] = lvl >= 5
    fm["eligible_xray"] = lvl >= 3
    fm["eligible_ultrasound"] = lvl >= 3
    fm["eligible_patient_monitor"] = lvl >= 3
    fm["equipment_eligible_any"] = (
        fm["eligible_hemodialysis"] | fm["eligible_icu_ultrasound"] if False else
        fm[["eligible_hemodialysis", "eligible_icu_ventilator", "eligible_anesthesia_theatre",
            "eligible_mri_ct", "eligible_xray", "eligible_ultrasound", "eligible_patient_monitor"]].any(axis=1)
    )
    # Facilities with unknown/missing level: mark eligibility as unknown, not False,
    # so they aren't silently excluded from downstream joins
    unknown_level = lvl.isna()
    elig_cols = ["eligible_hemodialysis", "eligible_icu_ventilator", "eligible_anesthesia_theatre",
                 "eligible_mri_ct", "eligible_xray", "eligible_ultrasound", "eligible_patient_monitor"]
    for col in elig_cols:
        fm[col] = fm[col].astype("boolean")  # nullable boolean dtype, supports pd.NA
        fm.loc[unknown_level, col] = pd.NA

    fm.to_csv(OUT_DIR / "facility_master.csv", index=False)

    print(f"Primary source rows: {len(primary):,}")
    print(f"Secondary source rows (not merged, kept for cross-check): {len(secondary):,}")
    print(f"Dropped (missing name/county): {dropped:,}")
    print(f"Facility master rows: {len(fm):,}")
    print(f"Counties covered: {fm['county'].nunique():,}")
    print(f"Level 4+ (dialysis/ICU-eligible): {(lvl>=4).sum():,}")
    print(f"Level 5+ (MRI/CT-eligible): {(lvl>=5).sum():,}")
    print(f"Unknown level: {unknown_level.sum():,}")
    print(f"Saved to: {(OUT_DIR / 'facility_master.csv').resolve()}")
    return fm


if __name__ == "__main__":
    build_facility_master()
