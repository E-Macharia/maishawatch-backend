# VitalAsset — Data Contract (Week 1)

Written so Brenda's scenario-rationale work and Paul's dashboard wiring build against the
same column names as the actual pipeline output, not a guess from opening a CSV.

## facility_master.csv (`data/processed/facility_master.csv`)
One row per real Kenyan health facility (KMHFR-derived, 12,394 facilities, 47 counties).

| Column | Notes |
|---|---|
| `facility_id` | Stable join key. Real KMHFR code where available, else `GEN-######`. |
| `facility_name`, `county`, `constituency`, `sub_county`, `ward` | Location fields. |
| `keph_level`, `keph_level_numeric` | Facility level (2=dispensary … 6=national referral). |
| `facility_type`, `facility_type_category`, `owner`, `owner_type` | Classification fields. |
| `beds`, `cots`, `beds_and_cots` | Capacity fields. |
| `eligible_hemodialysis`, `eligible_icu_ventilator`, `eligible_anesthesia_theatre` | Boolean, True if `keph_level_numeric >= 4`. `<NA>` if level unknown — not `False`. |
| `eligible_mri_ct` | Boolean, True if `keph_level_numeric >= 5`. |
| `eligible_xray`, `eligible_ultrasound`, `eligible_patient_monitor` | Boolean, True if `keph_level_numeric >= 3`. |

## equipment_master.csv (`scripts/generation/data/equipment_master.csv`)
One row per simulated equipment unit, placed on a real facility via `facility_id`.

| Column | Notes |
|---|---|
| `equipment_id` | `ME-#####` |
| `equipment_type` | One of 8 types (Hemodialysis, MRI, CT, Ultrasound, Ventilator, Anesthesia, X-Ray, Patient Monitor). |
| `facility_id`, `facility`, `county`, `keph_level` | Joined from facility_master — always eligibility-consistent with `equipment_type`. |
| `scenario_type` | `Normal` / `UsageDiscrepancy` / `MaintenanceNeglect` / both. |
| `scenario_rationale` | Text tying the scenario to a cited real case (MES audit, Naivasha, KNH radiotherapy, 125-hospital halt). **Placeholder text for now — Brenda's rationale doc is the authoritative version; this field should be replaced/expanded from that doc, not the other way around.** |
| `discrepancy_pct_target` | 0 for non-discrepancy equipment; 0.12–0.42 target under-reporting for flagged equipment. |

## usage_reporting_log.csv (`scripts/generation/data/usage_reporting_log.csv`)
Weekly counter-vs-register reconciliation — this is what feeds the discrepancy-detection metric.

| Column | Notes |
|---|---|
| `equipment_id`, `facility_id`, `week_start` | Composite key. |
| `counter_reported_hours` | Ground truth, derived from telemetry. |
| `register_reported_hours` | Simulated paper-register figure; under-reports for flagged cases. |
| `discrepancy_pct` | `(counter - register) / counter`. |
| `is_labeled_discrepancy_case` | Ground-truth label for evaluating the discrepancy-flagging model. |

## sensor_telemetry.csv / predictive_maintenance_dataset.csv
Hourly readings per equipment, 90 days. Key columns: `risk_score`, `degradation_index`,
`condition_status`, `failure`, `rul_hours`. See `scripts/generation/README.md` for the full
column list — not duplicated here since it's already documented there.

## cmapss_fd001_{train,test,rul}.csv (`data/processed/`)
NASA C-MAPSS FD001, used for breakdown-risk **method validation only** — not joined to Kenya
facility/equipment data.

| Column | Notes |
|---|---|
| `unit_number`, `cycle` | Engine unit ID and operating cycle. |
| `op_setting_1..3` | Operational settings. |
| `sensor_1..21` | Sensor readings. |
| `RUL` | Remaining useful life (train set only — computed as max_cycle - cycle per unit; test set RUL comes from `cmapss_fd001_rul.csv`, one value per unit). |

## Open items
- `keph_level` is missing for 1 facility in the master (kept as `<NA>`, not dropped).
- Equipment/facility coordinates are **county-centroid approximations**, not surveyed
  facility GPS — fine for a demo map, don't present as precise.
