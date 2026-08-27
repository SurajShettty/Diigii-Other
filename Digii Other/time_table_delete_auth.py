import sys
import pandas as pd
import requests
import json
import io

#  Force UTF-8 for stdout and stderr (Windows-safe)
sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(
    sys.stderr.buffer, encoding='utf-8', errors='ignore')

# Read Excel file safely
instances = pd.read_excel(
    r"C:\Users\suraj\Downloads\delete_slots.xlsx")

# API endpoint
report_api_path = "/api/timetable/delete"

for idx, row in instances.iterrows():
    base_url = "undefined"
    try:
        # Read required fields
        lesson_id = int(row['lesson_id'])
        base_url = str(row['url']).strip().rstrip('/')
        auth_token = str(row['auth_token']).strip()

        # Always fixed values
        recurrence = "this_slot"
        comment = None

        # Ensure proper URL
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url

        #  Correct request body
        report_body = {
            "id": lesson_id,
            "recurrence": recurrence,
            "comment": comment
        }

        report_url = f"{base_url}{report_api_path}"
        headers = {
            'Auth-token': auth_token,
            'Content-Type': 'application/json'
        }

        #  Use DELETE method with body
        response = requests.delete(
            report_url,
            headers=headers,
            data=json.dumps(report_body),
            timeout=30
        )

        # Safe print output
        safe_text = response.text.encode(
            "utf-8", "ignore").decode("utf-8", "ignore")
        print(f"[{base_url}]  Response: {safe_text[:250]}")

    except Exception as e:
        err_text = str(e).encode("utf-8", "ignore").decode("utf-8", "ignore")
        print(f"[{base_url}]  Error: {err_text}")

print("\n Bulk timetable delete completed without encoding errors.")
