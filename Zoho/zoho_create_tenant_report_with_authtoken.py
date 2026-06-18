import pandas as pd
import requests
import json

# Read instance info + report details from Excel
# Excel must contain columns: module, reportId, reportName, active, url, auth_token
instances = pd.read_excel(r"C:\Users\suraj\OneDrive\Desktop\Book1.xlsx")

# API endpoint
report_api_path = "/api/analytics/report/tenant"

for idx, row in instances.iterrows():
    try:
        # Read report + instance details
        module = str(row['module']).strip()
        report_id = int(row['reportId'])
        report_name = str(row['reportName']).strip()
        active = bool(row['active'])
        base_url = str(row['url']).strip().rstrip('/')
        auth_token = str(row['auth_token']).strip()

        # Ensure proper URL format
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            base_url = "https://" + base_url

        # Step 1: Prepare report body
        report_body = {
            "reports": [
                {
                    "module": module,
                    "reportId": report_id,
                    "reportName": report_name,
                    "active": active
                }
            ]
        }

        # Step 2: Call the report API
        report_url = f"{base_url}{report_api_path}"
        report_headers = {
            'Auth-token': auth_token,
            'Content-Type': 'application/json'
        }

        report_resp = requests.put(
            report_url, headers=report_headers, data=json.dumps(report_body), timeout=30
        )

        print(f"[{base_url}] ✅ Report Response: {report_resp.text[:200]}")

    except Exception as e:
        print(f"[{base_url}] ⚠️ Error: {e}")

print("\nBulk API script completed.")
