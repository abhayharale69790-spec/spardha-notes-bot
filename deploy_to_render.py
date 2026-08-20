"""Automated Render Deployment Script using Render REST API."""

import json
import sys
import httpx

RENDER_API_BASE = "https://api.render.com/v1"


def deploy(render_api_key: str):
    headers = {
        "Authorization": f"Bearer {render_api_key.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print("1. Checking Render Owners / Workspaces...")
    r_owners = httpx.get(f"{RENDER_API_BASE}/owners", headers=headers, timeout=20.0)
    if r_owners.status_code != 200:
        print(f"   Error fetching owners: {r_owners.status_code} - {r_owners.text}")
        return False

    owners = r_owners.json()
    if not owners:
        print("   No owner accounts found on Render.")
        return False

    owner_id = owners[0]["owner"]["id"]
    print(f"   Found Owner ID: {owner_id} ({owners[0]['owner'].get('name', 'Personal')})")

    print("2. Creating Web Service on Render...")
    payload = {
        "type": "web_service",
        "name": "spardha-notes-bot",
        "ownerId": owner_id,
        "repo": "https://github.com/abhayharale69790-spec/spardha-notes-bot",
        "branch": "main",
        "autoDeploy": "yes",
        "serviceDetails": {
            "env": "python",
            "plan": "free",
            "region": "oregon",
            "healthCheckPath": "/health",
            "envSpecificDetails": {
                "buildCommand": "pip install --upgrade pip && pip install -r requirements.txt",
                "startCommand": "python main.py",
            },
            "envVars": [
                {"key": "PYTHON_VERSION", "value": "3.11.8"},
                {"key": "BOT_TOKEN", "value": "8880658335:AAFf6yjx9L0SsXKoY-ucCX8soq-s1LRPTNs"},
                {"key": "MAIN_CHANNEL_ID", "value": "-1004297360223"},
                {"key": "STAGING_CHANNEL_ID", "value": "-1004475827003"},
                {"key": "BACKUP_CHANNEL_ID", "value": "-1004387550439"},
                {"key": "ADMIN_USER_IDS", "value": "8691719772"},
                {"key": "DATABASE_URL", "value": "sqlite+aiosqlite:///data/study_platform.db"},
                {"key": "SCRAPE_INTERVAL_MINUTES", "value": "15"},
                {"key": "BACKUP_INTERVAL_HOURS", "value": "24"},
            ],
        },
    }

    r_create = httpx.post(f"{RENDER_API_BASE}/services", headers=headers, json=payload, timeout=30.0)
    if r_create.status_code in (200, 201):
        svc_data = r_create.json()
        svc = svc_data.get("service", {})
        print("3. Service successfully deployed to Render!")
        print(f"   Service ID: {svc.get('id')}")
        print(f"   Service Name: {svc.get('name')}")
        print(f"   Live URL: {svc.get('serviceDetails', {}).get('url', 'Will appear after build')}")
        return True
    else:
        print(f"   Render API Response: {r_create.status_code} - {r_create.text}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python deploy_to_render.py <RENDER_API_KEY>")
        sys.exit(1)
    deploy(sys.argv[1])
