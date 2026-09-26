# MaishaWatch Backend — Complete Integrated Build

This package contains the current MaishaWatch backend with RBAC, hospital/facility management, equipment registry, maintenance work orders, notifications/email, manual alerts, system-generated ML alerts, failure prediction APIs and RUL prediction.

## Run

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.api.main:app --reload
```

API documentation: `http://127.0.0.1:8000/docs`

## Default administrator

Configured through environment variables:

- `DEFAULT_ADMIN_EMAIL` (default: `machariaevans636@gmail.com`)
- `DEFAULT_ADMIN_PASSWORD` (default: `Admin@123`)

Change these before deployment.

## Gmail SMTP

Set:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=maishawatch@gmail.com
SMTP_PASSWORD=<Gmail App Password>
SMTP_FROM=maishawatch@gmail.com
SMTP_USE_TLS=true
```

Use a Gmail App Password, not the normal account password.

## ML

Bundled models:

- `models/failure_model_24h.pkl`
- `models/failure_model_72h.pkl`
- `models/failure_model_168h.pkl`
- `models/rul_model.pkl`
- `models/rul_features.pkl`

The models use `data/predictive_maintenance_dataset.csv` as their inference source, so the deployment package does not duplicate the same 324,000 telemetry rows three times.

The prediction feature builder uses the model's `feature_names_in_` and reindexes one-hot encoded inputs to the exact expected feature set.

## Alert pipeline

### Manual

`POST /alerts` creates a persisted `MANUAL` alert and immediately creates in-app notifications and attempts email delivery for users eligible under RBAC.

### System / ML

`POST /equipment/evaluate` evaluates the three failure horizons plus RUL. If the result reaches an alert threshold, `app/engines/alert_engine.py` persists a unique `SYSTEM` alert and sends role-specific notifications.

Existing active system alerts for the same equipment/type are updated rather than generating repeated alerts and email spam.

## Important alert rules

- Manual alerts can be PUT/PATCH edited and DELETE deleted by permitted roles.
- System-generated alerts cannot be edited or deleted through the manual CRUD endpoints.
- Facility-scoped users only see and receive alerts for their facility.
- National-scoped users can see and receive alerts across facilities.
- Every email alert also creates an unread in-app notification.
