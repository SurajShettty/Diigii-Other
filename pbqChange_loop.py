import requests
import pandas as pd
import time

# --- Path to your Excel file ---
FILE_PATH = r"C:\Users\suraj\OneDrive\Desktop\ukids.xlsx"

# --- Column in the sheet that holds the ukids ---
COLUMN_NAME = "ukid"

# --- Delay between calls (seconds) ---
DELAY_SECONDS = 10

# --- Auth token ---
authtoken = "ea948a68-2fd9-451f-825a-69296be70f70-af-ak"
headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

# Read ukids from the Excel sheet
df = pd.read_excel(FILE_PATH)
ukids = df[COLUMN_NAME].dropna().tolist()

total = len(ukids)
print(f"Found {total} ukids. Starting...")

# Iterate ukid over each row from the sheet
for i, ukid in enumerate(ukids, start=1):
    # API url with the ukid passed as the param
    url = f'https://ttdjc.digiicampus.com/api/academicFee/v2/script/pbqChange?ukid={ukid}'

    # Fire the PUT request
    response = requests.put(url, headers=headers)

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"[{i}/{total}] ukid {ukid} was successful.")
    else:
        print(f"[{i}/{total}] ukid {ukid} failed with status code {response.status_code}.")

    # 10-second delay between calls (skip after the last row)
    if i < total:
        time.sleep(DELAY_SECONDS)

print("Done.")
