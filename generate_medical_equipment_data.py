from pathlib import Path
import random
import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
N_EQUIPMENT = 150
DAYS = 90
SAMPLES_PER_DAY = 24
FAILURE_RATE = 0.18            # fraction of equipment on a maintenance-neglect -> breakdown arc
DISCREPANCY_RATE = 0.28        # fraction of equipment with a usage-reporting discrepancy

random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_KE")
fake.seed_instance(SEED)

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)
REFERENCE_DIR = Path("reference")

PROFILES = {
    "Hemodialysis": (["Fresenius","B. Braun","Nikkiso"],["5008S","6008","Dialog+"],"Renal Unit",(36,38.5),(0.15,1.2),(180,260),(450,650),(1,2.5),(35,65)),
    "MRI": (["Siemens","GE Healthcare","Philips"],["MAGNETOM","SIGNA","Ingenia"],"Radiology",(18,24),(0.05,0.8),(90,120),(10,40),(20,80),(35,60)),
    "CT": (["GE Healthcare","Siemens","Canon"],["Revolution","SOMATOM","Aquilion"],"Radiology",(19,25),(0.1,1.5),(95,125),(15,60),(15,90),(30,65)),
    "Ultrasound": (["GE Healthcare","Philips","Mindray"],["LOGIQ","EPIQ","DC-70"],"Imaging",(20,28),(0.05,0.7),(90,115),(5,25),(0.2,1.2),(30,70)),
    "Ventilator": (["Drager","Hamilton","Medtronic"],["Evita","C6","PB980"],"ICU",(20,30),(0.1,1.0),(10,40),(5,80),(0.2,1.5),(30,75)),
    "Anesthesia": (["Drager","GE Healthcare","Mindray"],["Perseus","Aisys","WATO"],"Operating Theatre",(19,27),(0.05,0.9),(5,35),(2,60),(0.2,1.8),(30,70)),
    "X-Ray": (["Siemens","GE Healthcare","Philips"],["Ysio","Definium","DigitalDiagnost"],"Radiology",(20,27),(0.05,1.1),(90,125),(5,30),(5,60),(30,65)),
    "Patient Monitor": (["Philips","GE Healthcare","Mindray"],["IntelliVue","CARESCAPE","BeneVision"],"ICU",(20,30),(0.05,0.6),(90,120),(0,10),(0.05,0.5),(30,75)),
}

# Which real-facility eligibility column each equipment type must satisfy
# (mirrors the eligibility flags computed in the facility-master pipeline).
EQUIPMENT_ELIGIBILITY_COL = {
    "Hemodialysis": "eligible_hemodialysis",
    "Ventilator": "eligible_icu_ventilator",
    "Anesthesia": "eligible_anesthesia_theatre",
    "MRI": "eligible_mri_ct",
    "CT": "eligible_mri_ct",
    "X-Ray": "eligible_xray",
    "Ultrasound": "eligible_ultrasound",
    "Patient Monitor": "eligible_patient_monitor",
}

# Approximate county-headquarters coordinates. The facility master has no facility-level
# geocoding, so equipment is placed at its county's approximate centroid -- fine for a
# demo map, but don't present these as surveyed facility coordinates.
COUNTY_CENTROIDS = {
    "Mombasa": (-4.0435, 39.6682), "Kwale": (-4.1747, 39.4521), "Kilifi": (-3.6305, 39.8499),
    "Tana River": (-1.4998, 40.0296), "Lamu": (-2.2717, 40.9020), "Taita Taveta": (-3.3960, 38.5535),
    "Garissa": (-0.4569, 39.6583), "Wajir": (1.7471, 40.0573), "Mandera": (3.9366, 41.8550),
    "Marsabit": (2.3284, 37.9899), "Isiolo": (0.3546, 37.5822), "Meru": (0.0470, 37.6556),
    "Tharaka-Nithi": (-0.3000, 37.8833), "Embu": (-0.5310, 37.4500), "Kitui": (-1.3667, 38.0167),
    "Machakos": (-1.5177, 37.2634), "Makueni": (-1.8039, 37.6202), "Nyandarua": (-0.1833, 36.5000),
    "Nyeri": (-0.4201, 36.9476), "Kirinyaga": (-0.5000, 37.2833), "Murang'A": (-0.7833, 37.1500),
    "Muranga": (-0.7833, 37.1500), "Kiambu": (-1.1714, 36.8356), "Turkana": (3.1167, 35.6000),
    "West Pokot": (1.6167, 35.1167), "Samburu": (1.1050, 36.6900), "Trans Nzoia": (1.0157, 35.0062),
    "Uasin Gishu": (0.5204, 35.2699), "Elgeyo-Marakwet": (0.6667, 35.5000), "Elgeyo Marakwet": (0.6667, 35.5000),
    "Nandi": (0.1833, 35.1167), "Baringo": (0.4667, 35.9667), "Laikipia": (0.0167, 37.0667),
    "Nakuru": (-0.3031, 36.0800), "Narok": (-1.0833, 35.8667), "Kajiado": (-1.8500, 36.7833),
    "Kericho": (-0.3676, 35.2861), "Bomet": (-0.7833, 35.3333), "Kakamega": (0.2827, 34.7519),
    "Vihiga": (0.0833, 34.7167), "Bungoma": (0.5635, 34.5606), "Busia": (0.4608, 34.1116),
    "Siaya": (0.0607, 34.2881), "Kisumu": (-0.0917, 34.7680), "Homa Bay": (-0.5167, 34.4500),
    "Migori": (-1.0634, 34.4731), "Kisii": (-0.6773, 34.7796), "Nyamira": (-0.5633, 34.9358),
    "Nairobi": (-1.2864, 36.8172),
}

def clip_normal(mean, sd, lo, hi):
    return float(np.clip(np.random.normal(mean, sd), lo, hi))

DISCREPANCY_RATIONALE = (
    "Usage-reporting discrepancy modeled on the 2026 national MES dialysis audit finding: "
    "machine usage counters showed materially more work performed than hospitals' paper "
    "registers recorded, by more than 30% in some cases."
)
NEGLECT_RATIONALE_POOL = [
    "Maintenance-neglect-to-breakdown pattern modeled on the January 2025 Naivasha "
    "sub-county hospital dialysis machine breakdown, which forced patients to seek care elsewhere.",
    "Maintenance-neglect-to-breakdown pattern modeled on the 2025 Kenyatta National Hospital "
    "radiotherapy machine failure that disrupted national oncology services.",
    "Maintenance-neglect-to-breakdown pattern modeled on the MES 125-hospital equipment-halt "
    "case, where machines across facilities ground to a halt due to lack of maintenance.",
]

def load_eligible_facilities():
    """Load the real facility master and split it into an eligible-facility pool per
    equipment type, based on the eligibility flags computed in the facility pipeline."""
    fm = pd.read_csv(REFERENCE_DIR / "facility_master.csv")
    fm["county"] = fm["county"].astype(str).str.strip()

    pools = {}
    for eq_type, col in EQUIPMENT_ELIGIBILITY_COL.items():
        eligible = fm[fm[col] == True].copy()  # noqa: E712 (nullable boolean -- excludes NA/False)
        if eligible.empty:
            # Fall back to the full facility list if a type has no eligible rows
            # (shouldn't happen given the Level thresholds, but guards against it)
            eligible = fm.copy()
        pools[eq_type] = eligible.reset_index(drop=True)
    return fm, pools

def facility_coords(county):
    return COUNTY_CENTROIDS.get(county, COUNTY_CENTROIDS["Nairobi"])

def make_equipment(pools):
    types = list(PROFILES)
    weights = [18, 8, 14, 12, 15, 10, 10, 8]
    rows = []
    n_discrepancy = max(1, int(N_EQUIPMENT * DISCREPANCY_RATE))
    n_neglect = max(1, int(N_EQUIPMENT * FAILURE_RATE))
    discrepancy_ids = set(random.sample(range(1, N_EQUIPMENT + 1), n_discrepancy))
    neglect_ids = set(random.sample(range(1, N_EQUIPMENT + 1), n_neglect))

    for i in range(1, N_EQUIPMENT + 1):
        typ = random.choices(types, weights=weights)[0]
        manufacturers, models, dept, *_ = PROFILES[typ]

        pool = pools[typ]
        fac_row = pool.sample(n=1, random_state=random.randint(0, 10_000_000)).iloc[0]
        facility = fac_row["facility_name"]
        county = fac_row["county"]
        facility_id = fac_row["facility_id"]
        keph_level = fac_row.get("keph_level", None)
        lat, lon = facility_coords(county)

        is_discrepancy = i in discrepancy_ids
        is_neglect = i in neglect_ids
        if is_discrepancy and is_neglect:
            scenario_type = "UsageDiscrepancy+MaintenanceNeglect"
            rationale = DISCREPANCY_RATIONALE + " " + random.choice(NEGLECT_RATIONALE_POOL)
        elif is_discrepancy:
            scenario_type = "UsageDiscrepancy"
            rationale = DISCREPANCY_RATIONALE
        elif is_neglect:
            scenario_type = "MaintenanceNeglect"
            rationale = random.choice(NEGLECT_RATIONALE_POOL)
        else:
            scenario_type = "Normal"
            rationale = "No injected scenario; represents routine operating condition."

        rows.append({
            "equipment_id": f"ME-{i:05d}",
            "equipment_type": typ,
            "manufacturer": random.choice(manufacturers),
            "model": random.choice(models),
            "serial_number": fake.bothify("SN-????-########").upper(),
            "facility_id": facility_id, "facility": facility, "county": county,
            "keph_level": keph_level, "department": dept,
            "latitude": lat, "longitude": lon,
            "installation_date": fake.date_between("-8y", "-1y"),
            "last_maintenance_date": fake.date_between("-180d", "today"),
            "operating_hours_at_start": random.randint(1000, 30000),
            "maintenance_interval_days": random.choice([30, 60, 90, 120, 180]),
            "criticality": random.choice(["Low", "Medium", "High", "Critical"]),
            "scenario_type": scenario_type,
            "scenario_rationale": rationale,
            "discrepancy_pct_target": round(random.uniform(0.12, 0.42), 3) if is_discrepancy else 0.0,
        })
    return pd.DataFrame(rows)

def make_telemetry(eqdf):
    timestamps = pd.date_range("2026-01-01", periods=DAYS*SAMPLES_PER_DAY, freq="h")
    failing = set(eqdf.loc[eqdf.scenario_type.str.contains("MaintenanceNeglect"), "equipment_id"])
    rows = []
    for _, eq in eqdf.iterrows():
        typ = eq.equipment_type
        _,_,dept,temp,vib,press,flow,power,humidity = PROFILES[typ]
        start = random.randint(int(len(timestamps)*.45), int(len(timestamps)*.8)) if eq.equipment_id in failing else len(timestamps)+1
        tm, vm, pm, fm, wm = map(lambda x:(x[0]+x[1])/2,[temp,vib,press,flow,power])
        for i, ts in enumerate(timestamps):
            util = clip_normal(.72 if 7 <= ts.hour <= 19 else .30,.12 if 7 <= ts.hour <= 19 else .10,.05,1)
            if ts.dayofweek >= 5: util *= random.uniform(.8,.95)
            deg = min(1,(i-start)/max(1,len(timestamps)-start)) if i>=start else 0
            temperature = tm + .8*np.sin(2*np.pi*ts.hour/24)+1.8*util+np.random.normal(0,.25)+deg*random.uniform(2,5)
            vibration = vm+.1*util+np.random.normal(0,max(.01,vm*.05))+deg*random.uniform(max(.2,vm*.7),max(.5,vm*2.5))
            pressure = pm+.05*pm*util+np.random.normal(0,max(1,pm*.025))+deg*np.random.normal(0,max(1,pm*.12))
            flow_rate = fm*(.85+.25*util)+np.random.normal(0,max(.1,fm*.04))+deg*np.random.normal(0,max(.2,fm*.1))
            power_consumption = wm*(.75+.35*util)+np.random.normal(0,max(.01,wm*.04))+deg*random.uniform(max(.02,wm*.1),max(.05,wm*.4))
            hum = clip_normal((humidity[0]+humidity[1])/2,max(1,(humidity[1]-humidity[0])*.08),max(5,humidity[0]-15),min(95,humidity[1]+15))
            ta=max(0,(temperature-tm)/max(.1,temp[1]-temp[0]))
            va=max(0,(vibration-vm)/max(.1,vib[1]-vib[0]))
            pa=abs(pressure-pm)/max(1,press[1]-press[0])
            fa=abs(flow_rate-fm)/max(1,flow[1]-flow[0])
            wa=max(0,(power_consumption-wm)/max(.1,power[1]-power[0]))
            risk=float(np.clip(.24*ta+.28*va+.18*pa+.15*fa+.15*wa,0,1))
            risk=float(np.clip(.65*risk+.55*deg+.10*( (ts.normalize()-pd.Timestamp(eq.last_maintenance_date)).days >= eq.maintenance_interval_days),0,1))
            status="Critical" if risk>=.8 else "High" if risk>=.6 else "Moderate" if risk>=.35 else "Normal"
            failure=int(eq.equipment_id in failing and deg>.8 and random.random()<max(0,(deg-.72)*.4+max(0,risk-.75)*.45))
            if failure: code,op="E-CRITICAL","Failed"
            elif risk>=.8: code,op=random.choice(["W-VIBRATION","W-TEMPERATURE","W-PRESSURE","W-FLOW","W-POWER"]),"Warning"
            elif risk>=.6: code,op="W-PREDICTIVE","Degraded"
            else: code,op="NONE","Normal"
            rows.append({
                "timestamp":ts,"equipment_id":eq.equipment_id,"equipment_type":typ,
                "facility_id":eq.facility_id,"facility":eq.facility,
                "county":eq.county,"department":dept,
                "temperature":round(temperature,3),"vibration":round(max(0,vibration),4),"pressure":round(pressure,3),
                "flow_rate":round(max(0,flow_rate),3),"power_consumption":round(max(0,power_consumption),3),"humidity":round(hum,2),
                "utilization_rate":round(util,3),"operating_hours":round(eq.operating_hours_at_start+i/24*util,2),
                "days_since_maintenance":max(0,(ts.normalize()-pd.Timestamp(eq.last_maintenance_date)).days),
                "maintenance_due":int((ts.normalize()-pd.Timestamp(eq.last_maintenance_date)).days>=eq.maintenance_interval_days),
                "temperature_anomaly":round(ta,4),"vibration_anomaly":round(va,4),"pressure_instability":round(pa,4),
                "flow_deviation":round(fa,4),"power_anomaly":round(wa,4),"degradation_index":round(deg,4),
                "risk_score":round(risk,4),"condition_status":status,"error_code":code,"operational_status":op,
                "failure":failure,"rul_hours":0 if failure else int(max(1,(1-deg)*1500+(1-risk)*800))
            })
    return pd.DataFrame(rows)

def make_usage_reporting_log(eqdf, tele):
    tele = tele.copy()
    tele["week"] = tele["timestamp"].dt.to_period("W").apply(lambda p: p.start_time)
    weekly = (tele.sort_values("timestamp")
                   .groupby(["equipment_id", "week"])["operating_hours"]
                   .agg(["first", "last"])
                   .reset_index())
    weekly["counter_hours_delta"] = (weekly["last"] - weekly["first"]).clip(lower=0)

    rows = []
    for _, eq in eqdf.iterrows():
        eq_weeks = weekly[weekly.equipment_id == eq.equipment_id]
        is_discrepancy = "UsageDiscrepancy" in eq.scenario_type
        target_pct = eq.discrepancy_pct_target if is_discrepancy else 0.0
        for _, wk in eq_weeks.iterrows():
            counter = round(float(wk.counter_hours_delta), 2)
            if is_discrepancy:
                pct = max(0.03, np.random.normal(target_pct, 0.04))
                register = round(max(0.0, counter * (1 - pct)), 2)
            else:
                register = round(max(0.0, counter + np.random.normal(0, max(1, counter * 0.02))), 2)
            discrepancy_pct = round((counter - register) / counter, 4) if counter > 0 else 0.0
            rows.append({
                "equipment_id": eq.equipment_id, "equipment_type": eq.equipment_type,
                "facility_id": eq.facility_id, "facility": eq.facility, "county": eq.county,
                "week_start": wk.week,
                "counter_reported_hours": counter,
                "register_reported_hours": register,
                "discrepancy_pct": discrepancy_pct,
                "is_labeled_discrepancy_case": is_discrepancy,
                "scenario_rationale": eq.scenario_rationale if is_discrepancy else "",
            })
    return pd.DataFrame(rows)

def make_maintenance(eqdf):
    rows=[]; mid=1
    actions=["General inspection","Sensor calibration","Filter replacement","Cooling system inspection","Bearing inspection","Pump inspection","Electrical inspection","Software diagnostics"]
    for _,eq in eqdf.iterrows():
        n_events = random.randint(0, 2) if "MaintenanceNeglect" in eq.scenario_type else random.randint(2, 5)
        for _ in range(n_events):
            rows.append({
                "maintenance_id":f"PM-{mid:06d}","equipment_id":eq.equipment_id,"equipment_type":eq.equipment_type,
                "facility_id":eq.facility_id,"facility":eq.facility,"county":eq.county,
                "maintenance_date":fake.date_between("-2y","today"),
                "maintenance_type":random.choice(["Preventive Maintenance","Corrective Maintenance","Inspection","Calibration","Component Replacement"]),
                "action_performed":random.choice(actions),"technician":fake.name(),
                "duration_hours":round(random.uniform(.5,8),2),"parts_cost":round(max(0,np.random.normal(25000,18000)),2),
                "downtime_hours":round(max(0,np.random.normal(2.5,2)),2),"maintenance_notes":fake.sentence()
            }); mid+=1
    return pd.DataFrame(rows)

def main():
    fm, pools = load_eligible_facilities()
    eq = make_equipment(pools)
    tele = make_telemetry(eq)
    usage_log = make_usage_reporting_log(eq, tele)
    maint = make_maintenance(eq)
    failures = tele[tele.failure==1].copy()
    failure_events = failures[["equipment_id","equipment_type","facility_id","facility","county","timestamp","error_code","risk_score"]].rename(columns={"timestamp":"failure_timestamp","error_code":"failure_mode"})
    failure_events = failure_events.merge(eq[["equipment_id","scenario_rationale"]], on="equipment_id", how="left")
    for c,v in {"severity":"Critical","downtime_hours":0.0,"estimated_repair_cost":0.0}.items(): failure_events[c]=v
    predictive = tele.merge(eq[["equipment_id","manufacturer","model","installation_date","criticality","maintenance_interval_days","scenario_type"]],on="equipment_id",how="left")

    eq.to_csv(OUTPUT_DIR/"equipment_master.csv",index=False)
    tele.to_csv(OUTPUT_DIR/"sensor_telemetry.csv",index=False)
    usage_log.to_csv(OUTPUT_DIR/"usage_reporting_log.csv",index=False)
    maint.to_csv(OUTPUT_DIR/"maintenance_history.csv",index=False)
    failure_events.to_csv(OUTPUT_DIR/"failure_events.csv",index=False)
    predictive.to_csv(OUTPUT_DIR/"predictive_maintenance_dataset.csv",index=False)

    print(f"Real facilities used: {eq.facility_id.nunique():,} (from {fm.shape[0]:,}-row facility master, {fm.county.nunique()} counties)")
    print(f"Equipment: {len(eq):,}")
    print(f"  - UsageDiscrepancy scenario: {(eq.scenario_type.str.contains('UsageDiscrepancy')).sum():,}")
    print(f"  - MaintenanceNeglect scenario: {(eq.scenario_type.str.contains('MaintenanceNeglect')).sum():,}")
    print(f"Telemetry rows: {len(tele):,}")
    print(f"Usage-reporting log rows: {len(usage_log):,}")
    print(f"Maintenance events: {len(maint):,}")
    print(f"Failure events: {len(failure_events):,}")
    print(f"Saved to: {OUTPUT_DIR.resolve()}")

if __name__=="__main__":
    main()
