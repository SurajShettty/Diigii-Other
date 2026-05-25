import pandas as pd
import requests
import json
import time

# ================= CONFIG =================
url = "https://vitaa.digiicampus.com/rest/users/deactivate/batch"

csv_file = r"C:\Users\suraj\OneDrive\Desktop\vitaa alumni ukids.csv"

AUTH_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzE1NjM5MzAiLCJ1a2lkIjoxNTYzOTMwLCJ1c2VyVHlwZSI6ImNvbGxwb2xsLWFkbWluIiwiaW50ZWdyYXRpb25Sb2xlcyI6W10sImh1Yk5hbWUiOiJodWItYXAtc291dGgtMS1kYjEiLCJ0ZW5hbnROYW1lIjoidml0YWEiLCJpbnN0aXR1dGVVcmwiOiJodHRwczovL3ZpdGFhLmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6NTY3LCJqdGkiOiJiZWU4ZjU4Ny1iY2NmLTRlY2YtYmM2Yi01YjgxNzVjYjgzYjkiLCJpYXQiOjE3Njk1Nzc1ODUsImV4cCI6MTc3MDIwMjE4NX0.OGNbzKsqfnu_0e_xi7nvNrZbXn81NaXbpodyOrg-iPhpVBBEXC6sMIWFWBpUXKm7BLu79fkbazsZYX39jCEfvFMoXlrjs88NTf53DgD2TslNtDH0jDzQUpxwev1x9wVUy7AvHS0xuMBuJ15DTS6y5fCsxAUpr2Pmxson2ijEOMpbMNyiIYpDNIQxW3yyWDWzZ4C-EDcDgX7s50qJH7nWz3JWTMl8vWKIcYBS2MZP4XFg44e7UBSupdYrZfDLIKIpW1HZNFzmis9q0Tyn-VmKD1cICT4x3shqyisqk53aPzvnHv-62Woe4qB3iCAHhxvaVo86xBdk3MJ1Sv5dNVuo2g"

headers = {
    "auth-token": AUTH_TOKEN,
    "Content-Type": "application/json"
}
# =========================================

# Load Csv
df = pd.read_csv(csv_file)

if "ukid" not in df.columns:
    raise Exception("Csv must contain 'ukid' column")

# Convert UKIDs to integer list
ukids = df["ukid"].dropna().astype(int).tolist()

if not ukids:
    raise Exception("No UKIDs found in Csv")

print(f"Total UKIDs to deactivate: {len(ukids)}")

# OPTIONAL: split into chunks (recommended if list is large)
CHUNK_SIZE = 50

success_chunks = 0
failed_chunks = []

for i in range(0, len(ukids), CHUNK_SIZE):
    chunk = ukids[i:i + CHUNK_SIZE]

    payload = json.dumps(chunk)

    response = requests.put(
        url,
        headers=headers,
        data=payload
    )

    if response.status_code == 200:
        success_chunks += 1
        print(f"✅ Deactivated UKIDs: {chunk}")
    else:
        failed_chunks.append(chunk)
        print(f"❌ Failed chunk {chunk}")
        print("Status:", response.status_code)
        print("Response:", response.text)

    time.sleep(10)  # avoid server overload

print("\n===== SUMMARY =====")
print("Total UKIDs:", len(ukids))
print("Successful chunks:", success_chunks)
print("Failed chunks:", len(failed_chunks))

if failed_chunks:
    print("Failed UKID chunks:", failed_chunks)
