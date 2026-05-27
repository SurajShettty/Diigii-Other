import requests
import pandas as pd
import time

# --------- Config ---------
API_URL = "https://demo.digiicampus.com/api/infrastructure/types/v2"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzM1ODg0IiwidWtpZCI6MzU4ODQsInVzZXJUeXBlIjoiY29sbHBvbGwtYWRtaW4iLCJpbnRlZ3JhdGlvblJvbGVzIjpbIkRDQiJdLCJpbnRlZ3JhdGlvbkZlYXR1cmVGbGFncyI6WyJESUdJSV9BSV9DSEFUQk9UIl0sImh1Yk5hbWUiOiJodWItYXAtc291dGgtMS1jb21tb24taHViIiwidGVuYW50TmFtZSI6ImRlbW8iLCJpbnN0aXR1dGVVcmwiOiJodHRwczovL2RlbW8uZGlnaWljYW1wdXMuY29tIiwiY29sbGVnZUlkIjozOSwianRpIjoiN2NhNzlhYzgtY2RjYS00MTBjLWE1MWQtMmE0ZWE1NTYzNzAyIiwiaWF0IjoxNzc5ODg0MzQ0LCJleHAiOjE3ODA1MDg5NDR9.N-2Ev5tJjaxEcFxgDcXc-CbJQdUQi7Ybd_2ZWuUCFiQLMn1u8l91xLNhjN97aOss95KA6t5mNjUWAgVPJ9G5Zn2RH4RG2E6qGM4gZjQjC0oFDNMbItu1WyFzqrjLTshbDt5Ps16cgqK0zCgbjyrIfRH_3q3oTasvYzYaC6lnA-RyhnXjRoqkqVjf5YJzXHVB8lCDqmoJJ_9Z-MuVOA_tj1DJ7kfLBVF1rnlH1K-XcWkO1Hj7gzdVkCPN0YISFhNKEQ3HwZ6kGr4LtLV0rr6mEQCOJfOqU9a7mjl_-UFDWxxKta10hOPCm-691u9NG4V7_fdN-iUFJrKV51mDF3fzgA"  # <-- paste your Auth-Token here
INPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\New XLSX Worksheet.xlsx"  # columns: type, fullDayBooking
DELAY_SECONDS = 10

headers = {
    "Content-Type": "application/json",
    "Auth-Token": AUTH_TOKEN,
}

# --------- Load Excel (expects columns: type, fullDayBooking) ---------
df = pd.read_excel(INPUT_FILE)

results = []

# --------- Loop through each row, post, then wait 10s ---------
for idx, row in df.iterrows():
    payload = {
        "type": str(row["type"]),
        "fullDayBooking": int(row["fullDayBooking"]),
        "checkInTime": "",
        "checkOutTime": "",
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        status = response.status_code
        body = response.text
        print(f"[{idx + 1}/{len(df)}] type={payload['type']} -> {status}")
        results.append({**payload, "status_code": status, "response": body})
    except Exception as e:
        print(f"[{idx + 1}/{len(df)}] type={payload['type']} -> ERROR: {e}")
        results.append({**payload, "status_code": "ERROR", "response": str(e)})

    # 10-second delay after each loop
    if idx < len(df) - 1:
        time.sleep(DELAY_SECONDS)

# --------- Save results ---------
out_file = INPUT_FILE.replace(".xlsx", "_results.xlsx")
pd.DataFrame(results).to_excel(out_file, index=False)
print(f"\nDone. Results saved to: {out_file}")
