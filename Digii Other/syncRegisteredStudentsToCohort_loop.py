import requests
import pandas as pd
import time

# --- Path to your Excel file ---
FILE_PATH = r"C:\Users\suraj\OneDrive\Desktop\courseIds.xlsx"

# --- Column in the sheet that holds the courseIds ---
COLUMN_NAME = "courseId"

# --- Fixed sessionId used for every call ---
SESSION_ID = 14

# --- Delay between calls (seconds) ---
DELAY_SECONDS = 10

# --- Auth token ---
authtoken = "ea948a68-2fd9-451f-825a-69296be70f70"
headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

BASE_URL = "https://wud.digiicampus.com/api/courseRegistration/scripts/syncRegisteredStudentsToCohort"

# Read courseIds from the Excel sheet
df = pd.read_excel(FILE_PATH)
course_ids = df[COLUMN_NAME].dropna().tolist()

total = len(course_ids)
print(f"Found {total} courseIds. Starting...")

# Iterate courseId over each row from the sheet
for i, course_id in enumerate(course_ids, start=1):
    course_id = int(course_id)
    url = f'{BASE_URL}?sessionId={SESSION_ID}&courseId={course_id}'

    # Fire the POST request
    response = requests.post(url, headers=headers)

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"[{i}/{total}] courseId {course_id} was successful.")
    else:
        print(f"[{i}/{total}] courseId {course_id} failed with status code {response.status_code}.")

    # Delay between calls (skip after the last row)
    if i < total:
        time.sleep(DELAY_SECONDS)

print("Done.")
