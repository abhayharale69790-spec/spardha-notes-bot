"""Automated Koyeb Deployment Script using Koyeb REST API."""

import json
import os
import sys
import httpx

KOYEB_API_BASE = "https://app.koyeb.com/v1"


def deploy(koyeb_api_token: str, app_name: str = "spardha-notes-bot"):
    headers = {
        "Authorization": f"Bearer {koyeb_api_token.strip()}",
        "Content-Type": "application/json",
    }

    print(f"1. Checking/Creating Koyeb App: {app_name}...")
    # Create or fetch App
    app_payload = {"name": app_name}
    r_app = httpx.post(f"{KOYEB_API_BASE}/apps", headers=headers, json=app_payload, timeout=20.0)
    
    if r_app.status_code == 200 or r_app.status_code == 201:
        app_id = r_app.json()["app"]["id"]
        print(f"   App created successfully! App ID: {app_id}")
    elif r_app.status_code == 409:
        # App already exists, get list
        r_list = httpx.get(f"{KOYEB_API_BASE}/apps", headers=headers, timeout=20.0)
        apps = r_list.json().get("apps", [])
        app_id = next((a["id"] for a in apps if a["name"] == app_name), None)
        print(f"   App already exists. App ID: {app_id}")
    else:
        print(f"   Error creating app: {r_app.status_code} - {r_app.text}")
        return False

    print("2. Creating/Updating Koyeb Service with GitHub deployment...")
    service_payload = {
        "app_id": app_id,
        "definition": {
            "name": "study-bot-service",
            "type": "WEB",
            "git": {
                "repository": "github.com/abhayharale69790-spec/spardha-notes-bot",
                "branch": "main",
                "build_command": "",
                "run_command": "python main.py",
                "no_deploy_on_push": False,
            },
            "instance_types": [{"type": "nano"}],
            "regions": ["fra"],
            "scalings": [{"min": 1, "max": 1}],
            "ports": [{"port": 8000, "protocol": "http"}],
            "routes": [{"path": "/", "port": 8000}],
            "health_checks": [
                {
                    "http": {"path": "/health", "port": 8000},
                    "grace_period": 15,
                    "interval": 30,
                    "restart_limit": 3,
                    "timeout": 5,
                }
            ],
            "env": [
                {"key": "BOT_TOKEN", "value": "8880658335:AAFf6yjx9L0SsXKoY-ucCX8soq-s1LRPTNs"},
                {"key": "MAIN_CHANNEL_ID", "value": "-1004297360223"},
                {"key": "STAGING_CHANNEL_ID", "value": "-1004475827003"},
                {"key": "BACKUP_CHANNEL_ID", "value": "-1004387550439"},
                {"key": "ADMIN_USER_IDS", "value": "8691719772"},
                {"key": "PORT", "value": "8000"},
                {"key": "DATABASE_URL", "value": "sqlite+aiosqlite:///data/study_platform.db"},
            ],
        },
    }

    r_svc = httpx.post(f"{KOYEB_API_BASE}/services", headers=headers, json=service_payload, timeout=30.0)
    if r_svc.status_code in (200, 201):
        svc_data = r_svc.json()
        print("3. Service deployed successfully to Koyeb!")
        print(f"   Service ID: {svc_data.get('service', {}).get('id')}")
        return True
    else:
        print(f"   Service deployment response: {r_svc.status_code} - {r_svc.text}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deploy_to_koyeb.py <KOYEB_API_TOKEN>")
        sys.exit(1)
    deploy(sys.argv[1])
