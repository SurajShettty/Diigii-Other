import requests
import json
import pandas as pd
from datetime import datetime

# --------- Step 1: Load Excel with instance URLs and credentials ---------
input_file = r"C:\Users\suraj\OneDrive\Desktop\input.xlsx"  # Change path as needed
df_input = pd.read_excel(input_file)

# --------- Step 2: Prepare Output Storage ---------
results = []

# --------- Step 3: Loop through each instance ---------
for idx, row in df_input.iterrows():
    base_url = row['instance_url'].strip().rstrip('/')  # Clean URL
    login_api_path = "/rest/service/authenticate"
    login_url = f"{base_url}{login_api_path}"

    username = row['username']
    password = row['password']

    login_payload = {
        "email": username,
        "password": password,
        "phone": None,
        "registrationId": None,
        "browser": "Firefox",
        "ip": 0,
        "operatingSystem": "Windows",
        "deviceId": "3131177739",
        "deviceType": "BROWSER",
        "rememberMe": False,
        "loginTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    login_headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=utf-8'
    }

    try:
        response = requests.post(
            login_url, headers=login_headers, json=login_payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        auth_token = (
            data.get('authToken') or
            data.get('auth-token') or
            data.get('token') or
            (data.get('res', {}).get('token') if isinstance(
                data.get('res'), dict) else None)
        )

        if not auth_token:
            print(f" [{base_url}] No token found.")
            results.append({
                "instance_url": base_url,
                "auth_token": " No token returned"
            })
        else:
            print(f" [{base_url}] Token received.")
            results.append({
                "instance_url": base_url,
                "auth_token": auth_token
            })

    except requests.exceptions.HTTPError as http_err:
        print(f"[{base_url}] HTTP error: {http_err}")
        results.append({
            "instance_url": base_url,
            "auth_token": f" HTTP error: {response.status_code}"
        })
    except Exception as e:
        print(f" [{base_url}] Unexpected error: {e}")
        results.append({
            "instance_url": base_url,
            "auth_token": f"Error: {e}"
        })

# --------- Step 4: Save Results to Excel ---------
df_output = pd.DataFrame(results)
output_file = r"C:\Users\suraj\OneDrive\Desktop\auth_tokens_output.xlsx"
df_output.to_excel(output_file, index=False)
print(f"\n All tokens saved to: {output_file}")
