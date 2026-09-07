# scripts/setup_test_environment.py (Fixed Version)
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"


def get_admin_token():
    """Get admin token"""
    url = f"{BASE_URL}/auth/token"
    data = {
        "grant_type": "password",
        "username": "calebmunyeks002@gmail.com",
        "password": "Admin@4321",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=data, headers=headers)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"❌ Failed to get token: {response.text}")
        return None


def create_hospital(token):
    """Create test hospital"""
    url = f"{BASE_URL}/facilities"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    hospital_data = {
        "facility_id": "HOSP-MAISHA-002",
        "facility_name": "Maisha Watch Test Hospital",
        "county": "Nairobi",
        "keph_level": "Level 5",
        "status": "ACTIVE",
    }

    response = requests.post(url, json=hospital_data, headers=headers)
    if response.status_code == 200:
        print("✅ Hospital created successfully!")
        return response.json()
    elif response.status_code == 409:
        print("ℹ️  Hospital already exists")
        return {"message": "Already exists"}
    else:
        print(f"❌ Failed to create hospital: {response.text}")
        return None


def create_equipment(token, equipment_data):
    """Create equipment using POST /equipment endpoint"""
    url = f"{BASE_URL}/equipment"  # Changed from /equipment/onboard
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.post(url, json=equipment_data, headers=headers)
    if response.status_code in [200, 201]:
        print(f"✅ Equipment created: {equipment_data.get('equipment_id')}")
        return response.json()
    elif response.status_code == 409:
        print(f"ℹ️  Equipment already exists: {equipment_data.get('equipment_id')}")
        return {"message": "Already exists"}
    else:
        print(
            f"❌ Failed to create {equipment_data.get('equipment_id')}: {response.text}"
        )
        return None


def create_user(token, user_data):
    """Create user"""
    url = f"{BASE_URL}/users"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.post(url, json=user_data, headers=headers)
    if response.status_code == 200:
        print(f"✅ User created: {user_data.get('email')}")
        return response.json()
    elif response.status_code == 409:
        print(f"ℹ️  User already exists: {user_data.get('email')}")
        return {"message": "Already exists"}
    else:
        print(f"❌ Failed to create user {user_data.get('email')}: {response.text}")
        return None


def get_all_facilities(token):
    """Get all facilities"""
    url = f"{BASE_URL}/facilities"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        facilities = response.json()
        print(f"\n📋 Facilities ({len(facilities)}):")
        for f in facilities:
            if f.get("facility_name"):
                print(
                    f"  - {f.get('facility_id')}: {f.get('facility_name')} ({f.get('county')})"
                )
        return facilities
    else:
        print(f"❌ Failed to get facilities: {response.text}")
        return None


def get_all_equipment(token):
    """Get all equipment"""
    url = f"{BASE_URL}/equipment"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        equipment_list = response.json()
        print(f"\n📋 Equipment ({len(equipment_list)}):")
        for e in equipment_list:
            if e.get("equipment_id", "").startswith("EQ-"):
                print(
                    f"  - {e.get('equipment_id')}: {e.get('equipment_type')} at {e.get('facility_id')}"
                )
        return equipment_list
    else:
        print(f"❌ Failed to get equipment: {response.text}")
        return None


def get_all_users(token):
    """Get all users"""
    url = f"{BASE_URL}/users"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        users = response.json()
        print(f"\n📋 Users ({len(users)}):")
        for u in users:
            print(
                f"  - {u.get('email')}: {u.get('role')} ({u.get('scope_id') or 'national'})"
            )
        return users
    else:
        print(f"❌ Failed to get users: {response.text}")
        return None


def main():
    print("=" * 60)
    print("Setting up Maisha Watch Test Environment")
    print("=" * 60)

    # Get admin token
    token = get_admin_token()
    if not token:
        print("❌ Could not get admin token")
        return

    # Create hospital (using a new ID)
    print("\n🏥 Creating hospital...")
    create_hospital(token)

    # Create equipment
    print("\n🔧 Creating equipment...")
    equipment_list = [
        {
            "equipment_id": "EQ-MRI-MAISHA-002",
            "facility_id": "HOSP-MAISHA-002",
            "equipment_type": "MRI Machine",
            "manufacturer": "Siemens Healthineers",
            "model": "MAGNETOM Vida 3T",
            "serial_number": "SN-MRI-MAISHA-002",
            "installation_date": "2024-01-15T10:00:00",
            "simulate_telemetry": True,
            "telemetry_interval_seconds": 60,
        },
        {
            "equipment_id": "EQ-CT-MAISHA-002",
            "facility_id": "HOSP-MAISHA-002",
            "equipment_type": "CT Scanner",
            "manufacturer": "GE Healthcare",
            "model": "Revolution CT",
            "serial_number": "SN-CT-MAISHA-002",
            "installation_date": "2024-02-01T14:00:00",
            "simulate_telemetry": True,
            "telemetry_interval_seconds": 60,
        },
        {
            "equipment_id": "EQ-VENT-MAISHA-002",
            "facility_id": "HOSP-MAISHA-002",
            "equipment_type": "Ventilator",
            "manufacturer": "Philips",
            "model": "V60",
            "serial_number": "SN-VENT-MAISHA-002",
            "installation_date": "2024-03-01T09:00:00",
            "simulate_telemetry": True,
            "telemetry_interval_seconds": 30,
        },
        {
            "equipment_id": "EQ-ULTRA-MAISHA-002",
            "facility_id": "HOSP-MAISHA-002",
            "equipment_type": "Ultrasound Machine",
            "manufacturer": "GE Healthcare",
            "model": "Voluson E10",
            "serial_number": "SN-ULTRA-MAISHA-002",
            "installation_date": "2024-04-01T08:00:00",
            "simulate_telemetry": True,
            "telemetry_interval_seconds": 120,
        },
        {
            "equipment_id": "EQ-MONITOR-MAISHA-002",
            "facility_id": "HOSP-MAISHA-002",
            "equipment_type": "Patient Monitor",
            "manufacturer": "Philips",
            "model": "IntelliVue MX800",
            "serial_number": "SN-MONITOR-MAISHA-002",
            "installation_date": "2024-05-01T09:00:00",
            "simulate_telemetry": True,
            "telemetry_interval_seconds": 60,
        },
    ]

    for eq in equipment_list:
        create_equipment(token, eq)
        time.sleep(0.5)

    # Create users (skip if they already exist)
    print("\n👤 Creating users...")
    users = [
        {
            "name": "Bruno Fernandes",
            "email": "reinhardkalesh@gmail.com",
            "password": "TempPass123!",
            "role": "facility_manager",
            "scope_type": "facility",
            "scope_id": "HOSP-MAISHA-002",
        },
        {
            "name": "Dr. Caleb Ostieno",
            "email": "calebostieno@gmail.com",
            "password": "TempPass123!",
            "role": "biomedical_engineer",
            "scope_type": "facility",
            "scope_id": "HOSP-MAISHA-002",
        },
        {
            "name": "Peter Kimani",
            "email": "inukatrust.demo@gmail.com",
            "password": "TempPass123!",
            "role": "maintenance_technician",
            "scope_type": "facility",
            "scope_id": "HOSP-MAISHA-002",
        },
        {
            "name": "Dr. Grace Wanjiru",
            "email": "watchmaisha@gmail.com",
            "password": "TempPass123!",
            "role": "clinician",
            "scope_type": "facility",
            "scope_id": "HOSP-MAISHA-002",
        },
        {
            "name": "Dr. James Omondi",
            "email": "james.omondi@maishawatch.com",
            "password": "TempPass123!",
            "role": "clinician",
            "scope_type": "facility",
            "scope_id": "HOSP-MAISHA-002",
        },
    ]

    for user in users:
        create_user(token, user)
        time.sleep(0.5)

    # Verify everything
    print("\n" + "=" * 60)
    print("Verifying Setup")
    print("=" * 60)

    get_all_facilities(token)
    get_all_equipment(token)
    get_all_users(token)

    print("\n" + "=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print("\n📝 Login Credentials for Test Users:")
    print("  - Facility Manager: reinhardkalesh@gmail.com / TempPass123!")
    print("  - Biomedical Engineer: calebostieno@gmail.com / TempPass123!")
    print("  - Maintenance Technician: inukatrust.demo@gmail.com / TempPass123!")
    print("  - Clinician 1: watchmaisha@gmail.com / TempPass123!")
    print("  - Clinician 2: james.omondi@maishawatch.com / TempPass123!")
    print(
        "\n⚠️  All users need to complete first-time login flow (OTP + password change)"
    )
    print("\n🔑 To complete first-time login for a user:")
    print("  1. Login with temporary password")
    print("  2. Get OTP from the response or database")
    print("  3. Verify OTP")
    print("  4. Change password")
    print("  5. Login with new password")


if __name__ == "__main__":
    main()
