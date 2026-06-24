import requests
import pandas as pd
import time

# Load Excel
df = pd.read_excel(
    r"C:\Users\suraj\Downloads\Templates for scripts and APIs (Excel & csv)\Intake bulk create template.xlsx",
    sheet_name="Sheet1"
)

headers = {
    "auth-token": "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzE4MTc1MjUiLCJ1a2lkIjoxODE3NTI1LCJ1c2VyVHlwZSI6ImNvbGxwb2xsLWFkbWluIiwiaW50ZWdyYXRpb25Sb2xlcyI6W10sImludGVncmF0aW9uRmVhdHVyZUZsYWdzIjpbXSwiaHViTmFtZSI6Imh1Yi1hcC1zb3V0aC0xLWRiMTkiLCJ0ZW5hbnROYW1lIjoiY3Jlc2NlbnQiLCJpbnN0aXR1dGVVcmwiOiJodHRwczovL2NyZXNjZW50LmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6NTk0LCJqdGkiOiJmOTBmYWU2NC04ZTMyLTQ5ZGQtYmU0OC01Y2U4YWE5OWM0ZWUiLCJpYXQiOjE3ODIyNzg2MzUsImV4cCI6MTc4MjkwMzIzNX0.eSLlnprt6ZYzon0BoV1QnF_0nzU7lxzK9YyGhwB8IBYLR7Kg6lwFGnWmugz2oBls1kun-zfOjkesACy03fPJVGleTgbRCxWAlGEjmUxH6v5vAF3Ran6HUIYV8_K6igba5PUlNMW3HdxK73NzWHXXUAtRBGVJWyOieDo_vOysfAoXkWl7Gya-qOJiGlJyBP4igxXnPqRG-royGtE1D9hskTVx_ASbAuEsFFDMUcUH1nAfyArhWXBzHMqLpvGdgUHDbbjdVD7zabAHWOPCZNTdmfXX09LuhA6MVYRXh32vbyf8_vIIl9PEEHNQxp4od0EiuxTpFMGHN2ykJMelDQKw7g",
    "Content-Type": "application/json"
}

# Loop unique department + batch
for _, row in df[["batchYear", "departmentId"]].drop_duplicates().iterrows():

    temp = df[
        (df["batchYear"] == row["batchYear"]) &
        (df["departmentId"] == row["departmentId"])
    ]

    # Prepare payload data safely
    temp2 = temp[["name", "batchYear", "programmeId", "newIntake"]].copy()

    # Clean Excel side effects
    temp2["name"] = temp2["name"].astype(str).str.strip()
    temp2["batchYear"] = temp2["batchYear"].astype(int)
    temp2["programmeId"] = temp2["programmeId"].astype(int)

    # Backend-friendly nulls
    temp2["durationFrom"] = None
    temp2["durationTo"] = None

    payload = {
        "intakes": temp2.to_dict(orient="records"),
        "intakesToBeDeleted": []
    }

    url = f"https://crescent.digiicampus.com/api/programme/intake/{row['departmentId']}/{row['batchYear']}/update"

    print("Calling:", url)
    print(payload)

    response = requests.put(
        url,
        headers=headers,
        json=payload   # <-- important (not data=)
    )

    print("Status:", response.status_code)
    print("Response:", response.text)
    time.sleep(10)
    # Remove break if you want all combinations processed
    # break