import requests
import pandas as pd
import time

# --------- Step 1: Config ---------
input_file = r"C:\Users\suraj\Downloads\Templates for scripts and APIs (Excel & csv)\Bulk Privilege Add.xlsx"  # Change path as needed
output_file = r"C:\Users\suraj\OneDrive\Desktop\admin_role_add_results.xlsx"

url = "https://university.digiicampus.com/rest/adminRole/add"

# Paste a fresh auth-token here before running
auth_token = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzEzMTA3MjciLCJ1a2lkIjoxMzEwNzI3LCJ1c2VyVHlwZSI6ImFkbWluaXN0cmF0b3IiLCJpbnRlZ3JhdGlvblJvbGVzIjpbXSwiaW50ZWdyYXRpb25GZWF0dXJlRmxhZ3MiOlsiRElHSUlfQUlfQ0hBVEJPVCIsIkRJR0lJX0FJX01DUF9BR0VOVCJdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtY29tbW9uLWh1YiIsInRlbmFudE5hbWUiOiJ1bml2ZXJzaXR5IiwiaW5zdGl0dXRlVXJsIjoiaHR0cHM6Ly91bml2ZXJzaXR5LmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6MjMxLCJqdGkiOiI4ZDZmZDU0Ny0xYjQxLTRhOGYtOTA5Ni0zNDEwNjhiMjllZTYiLCJpYXQiOjE3ODg4NDQzOTksImV4cCI6MTc4OTQ2ODk5OX0.HwjNfu1guLODF4TSY-V8s-p8NvUXn7xwpeYG4ZiljassQ6mOC8S69dH-B8AHu8qKnvnSsBf9WglM1LOBDLdwSxEKQUZ3uPewiC6VcGc2sklqdAn1i187siB-XztsbUAZ96R-7qiofjsSbQtOzbPvITpfDykwa8NwgUTLLx1Ql0NRMpX71izC41-T1-iZLW7E_CTsWSTXgoDZoFxvU3VUDHQ_vWCTTEloQDTQQxM9HJ6YLpxQf-aBCGR-b_vPD7qJ-LEo44NtqCS1SGKvHRKun9ZEnWfz4kgjp840EAbZQFa2sJwR25nlrabQsYLRritKDfUNVGUTjn_YQRoO_GA3dg"

headers = {
    "content-type": "application/json",
    "auth-token": auth_token
}

# --------- Step 2: Load Excel ---------
# Expected columns: emailPassed, role, rel, entityName, entityId
df = pd.read_excel(input_file)

results = []

# --------- Step 3: Loop through each row ---------
for index, row in df.iterrows():
    body = {
        "emailPassed": row["emailPassed"],
        "role": row["role"],
        "rel": row["rel"],
        "entityName": row["entityName"],
        "entityId": int(row["entityId"])
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)

        if response.status_code == 201:
            print(f"{body['emailPassed']} - role '{body['role']}' added successfully.")
            results.append({**body, "status": "Success", "response": response.text})
        else:
            print(f"{body['emailPassed']} - failed with status code {response.status_code}.")
            results.append({**body, "status": f"Failed ({response.status_code})", "response": response.text})

    except Exception as e:
        print(f"{body['emailPassed']} - error: {e}")
        results.append({**body, "status": "Error", "response": str(e)})

    time.sleep(1)

# --------- Step 4: Save results ---------
df_output = pd.DataFrame(results)
df_output.to_excel(output_file, index=False)
print(f"\nDone. Results saved to: {output_file}")


# SELECT ar.id,email AS emailPassed,ROLE AS role,ud.desc AS role_name,entity AS rel,entity_name AS entityName,entity_id AS entityId FROM admin_rights ar LEFT JOIN authenticator a ON a.ukid = ar.ukid LEFT JOIN UDC_04_ADMINROLE ud ON ud.`code` = ar.ROLE;