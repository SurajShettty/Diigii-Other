"""
zoho_dependents_export.py

Fetches all views in a Zoho Analytics workspace, keeps only those whose
viewType is "Table", calls the /dependents API for each of them, and
writes the results to a CSV file.

USAGE:
    1. Edit the CONFIG section below (output path, token, org ID, etc).
    2. Run:
         python zoho_dependents_export.py

NOTES:
    - Credentials are stored in the CONFIG section below. Since this file
      will contain a live OAuth token, avoid committing it to version
      control or sharing it as-is.
    - A small delay between calls is included to avoid hitting rate limits.
"""

import csv
import sys
import time

import requests


# ============================== CONFIG ==============================
OUTPUT_CSV_PATH = r"C:\Users\suraj\OneDrive\Desktop\dependents.csv"    # Path to the output CSV file
WORKSPACE_ID = "392249000004030742"   # Zoho Analytics workspace ID
VIEW_TYPE_FILTER = "Table"             # Only fetch dependents for views of this type
DELAY_SECONDS = 0.5                    # Delay between API calls

ZOHO_OAUTH_TOKEN = "1000.822a1acbb0df184df26196b0197321b1.269d35bd7d75dd8252a1ef82f02562e0"  # <-- put your token here
ZOHO_ORG_ID = "60034261789"                                  # <-- put your org ID here
# =====================================================================

VIEWS_URL = "https://analyticsapi.zoho.in/restapi/v2/workspaces/{workspace_id}/views"
BASE_URL = "https://analyticsapi.zoho.in/restapi/v2/workspaces/{workspace_id}/views/{view_id}/dependents"


def fetch_all_views(workspace_id: str, token: str, org_id: str) -> list:
    """Call the Zoho Analytics views API and return the raw list of view dicts."""
    url = VIEWS_URL.format(workspace_id=workspace_id)
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "ZANALYTICS-ORGID": org_id,
    }

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    inner = data.get("data", data) if isinstance(data, dict) else data
    views_list = None
    if isinstance(inner, dict):
        for key in ("views", "viewList"):
            if key in inner and isinstance(inner[key], list):
                views_list = inner[key]
                break
    elif isinstance(inner, list):
        views_list = inner

    if views_list is None:
        raise ValueError(f"Unexpected views response shape: {str(data)[:500]}")

    return views_list


def load_view_data(workspace_id: str, token: str, org_id: str, view_type_filter: str) -> list:
    """Fetch all views and return (view_id, view_name) pairs whose viewType matches view_type_filter."""
    views = fetch_all_views(workspace_id, token, org_id)

    pairs = []
    for view in views:
        view_type = str(view.get("viewType", view.get("type", ""))).strip()
        if view_type.lower() != view_type_filter.strip().lower():
            continue
        view_id = str(view.get("viewId", view.get("id", ""))).strip()
        view_name = str(view.get("viewName", view.get("name", ""))).strip()
        if view_id:
            pairs.append((view_id, view_name))
    return pairs


def fetch_dependents(view_id: str, workspace_id: str, token: str, org_id: str) -> dict:
    """Call the Zoho Analytics dependents API for a single view ID."""
    url = BASE_URL.format(workspace_id=workspace_id, view_id=view_id)
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "ZANALYTICS-ORGID": org_id,
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as e:
        return {"viewID": view_id, "status": "error", "error": str(e), "raw_response": ""}

    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError:
            return {
                "viewID": view_id,
                "status": "error",
                "error": "Non-JSON response",
                "raw_response": resp.text[:500],
            }
        return {"viewID": view_id, "status": "ok", "data": data}
    else:
        return {
            "viewID": view_id,
            "status": "error",
            "error": f"HTTP {resp.status_code}",
            "raw_response": resp.text[:500],
        }


def flatten_dependents(view_id: str, view_name: str, result: dict) -> list:
    """
    Turn one API result into one or more flat CSV rows.
    Zoho's dependents payload structure can vary; this handles the common
    case of a list of dependent view objects under result['data'].
    Falls back to a single summary row if the shape is unexpected.
    """
    rows = []

    if result["status"] != "ok":
        rows.append({
            "viewID": view_id,
            "viewName": view_name,
            "status": result["status"],
            "error": result.get("error", ""),
            "dependent_view_id": "",
            "dependent_view_name": "",
            "dependent_view_type": "",
            "raw_response": result.get("raw_response", ""),
        })
        return rows

    data = result["data"]

    # Try to locate a list of dependents inside the response payload.
    dependents_list = None
    if isinstance(data, dict):
        # Common Zoho pattern: {"data": {"views": [...]}}
        inner = data.get("data", data)
        if isinstance(inner, dict):
            for key in ("views", "dependents", "viewList"):
                if key in inner and isinstance(inner[key], list):
                    dependents_list = inner[key]
                    break
        elif isinstance(inner, list):
            dependents_list = inner

    if dependents_list:
        for dep in dependents_list:
            if isinstance(dep, dict):
                dep_type = dep.get("viewType", dep.get("type", ""))
                if str(dep_type).strip().lower() != "dashboard":
                    continue
                rows.append({
                    "viewID": view_id,
                    "viewName": view_name,
                    "status": "ok",
                    "error": "",
                    "dependent_view_id": dep.get("viewId", dep.get("id", "")),
                    "dependent_view_name": dep.get("viewName", dep.get("name", "")),
                    "dependent_view_type": dep_type,
                    "raw_response": "",
                })
    else:
        # Unknown shape — store the raw JSON for manual inspection.
        rows.append({
            "viewID": view_id,
            "viewName": view_name,
            "status": "ok",
            "error": "",
            "dependent_view_id": "",
            "dependent_view_name": "",
            "dependent_view_type": "",
            "raw_response": str(data)[:1000],
        })

    return rows


def main():
    token = ZOHO_OAUTH_TOKEN
    org_id = ZOHO_ORG_ID

    if not token or token.startswith("1000.xxxx") or not org_id:
        print("ERROR: Please set ZOHO_OAUTH_TOKEN and ZOHO_ORG_ID in the CONFIG section of this script.")
        sys.exit(1)

    print(f"Fetching views for workspace {WORKSPACE_ID} ...")
    view_data = load_view_data(WORKSPACE_ID, token, org_id, VIEW_TYPE_FILTER)
    print(f"Found {len(view_data)} view(s) of type '{VIEW_TYPE_FILTER}'.")

    all_rows = []
    for i, (view_id, view_name) in enumerate(view_data, start=1):
        print(f"[{i}/{len(view_data)}] Fetching dependents for view {view_id} ({view_name}) ...")
        result = fetch_dependents(view_id, WORKSPACE_ID, token, org_id)
        rows = flatten_dependents(view_id, view_name, result)
        all_rows.extend(rows)
        time.sleep(DELAY_SECONDS)

    if not all_rows:
        print("No results to write.")
        return

    fieldnames = [
        "viewID",
        "viewName",
        "status",
        "error",
        "dependent_view_id",
        "dependent_view_name",
        "dependent_view_type",
        "raw_response",
    ]

    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"Done. Wrote {len(all_rows)} row(s) to {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()