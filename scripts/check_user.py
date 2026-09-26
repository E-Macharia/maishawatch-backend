# scripts/delete_test_users.py
import requests
import json
import sys
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"


def get_admin_token():
    """Get admin token"""
    url = f"{BASE_URL}/auth/token"
    data = {
        "grant_type": "password",
        "username": "machariaevans636@gmail.com",
        "password": "Admin@123",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=data, headers=headers)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"❌ Failed to get token: {response.text}")
        return None


def get_user_id_by_email(token, email):
    """Get user ID by email"""
    url = f"{BASE_URL}/users"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        users = response.json()
        for user in users:
            if user.get("email") == email:
                return user.get("id")
    return None


def delete_user(token, user_id):
    """Delete a user (soft delete - set inactive)"""
    # Since we don't have a DELETE endpoint, we'll use PATCH to deactivate
    url = f"{BASE_URL}/users/{user_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    data = {"active": False}

    response = requests.patch(url, json=data, headers=headers)
    if response.status_code == 200:
        print(f"✅ User {user_id} deactivated")
        return True
    else:
        print(f"❌ Failed to deactivate user {user_id}: {response.text}")
        return False


def delete_user_permanently(token, user_id):
    """Permanently delete a user (SQLite direct - only if needed)"""
    # Note: This requires direct database access
    import sqlite3
    from app.core.paths import DB_FILE

    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        print(f"✅ User {user_id} permanently deleted from database")
        return True
    except Exception as e:
        print(f"❌ Failed to delete user: {e}")
        return False
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("Deleting Test Users")
    print("=" * 60)

    # Get admin token
    token = get_admin_token()
    if not token:
        print("❌ Could not get admin token")
        return

    # List of test users to delete
    test_users = [
        "reinhardkalesh@gmail.com",
        "calebostieno@gmail.com",
        "inukatrust.demo@gmail.com",
        "watchmaisha@gmail.com",
        "james.omondi@maishawatch.com",
    ]

    print("\n📋 Users to delete:")
    for email in test_users:
        print(f"  - {email}")

    print("\n" + "-" * 40)
    print("Deactivating users...")
    print("-" * 40)

    deleted_count = 0
    for email in test_users:
        user_id = get_user_id_by_email(token, email)
        if user_id:
            print(f"\n🗑️  Deleting {email} (ID: {user_id})...")
            if delete_user(token, user_id):
                deleted_count += 1
        else:
            print(f"\n⚠️  User not found: {email}")

    print("\n" + "=" * 60)
    print(f"✅ Deactivated {deleted_count} users")
    print("=" * 60)

    # Verify remaining users
    print("\n📋 Remaining users:")
    url = f"{BASE_URL}/users"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        users = response.json()
        for user in users:
            if user.get("active") == 1:
                print(f"  - {user.get('email')}: {user.get('role')} (Active)")
            else:
                print(f"  - {user.get('email')}: {user.get('role')} (Inactive)")


if __name__ == "__main__":
    main()
