import requests
import pandas as pd
import time

# Load Excel
df = pd.read_excel(
    r"C:\Users\suraj\Downloads\Templates for scripts and APIs (Excel & csv)\Intake bulk create template.xlsx",
    sheet_name="Sheet1"
)

headers = {
    "auth-token": "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzE1NzMzNzUiLCJ1a2lkIjoxNTczMzc1LCJ1c2VyVHlwZSI6ImFkbWluaXN0cmF0b3IiLCJpbnRlZ3JhdGlvblJvbGVzIjpbXSwiaW50ZWdyYXRpb25GZWF0dXJlRmxhZ3MiOltdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtZGIxIiwidGVuYW50TmFtZSI6InZpdGFhIiwiaW5zdGl0dXRlVXJsIjoiaHR0cHM6Ly92aXRhYS5kaWdpaWNhbXB1cy5jb20iLCJjb2xsZWdlSWQiOjU2NywianRpIjoiYjgyMDBkMzAtMTRlMi00MGRiLWIzNmYtNTJkMTBjNWQ0YjY3IiwiaWF0IjoxNzc4MDc4Njc3LCJleHAiOjE3Nzg3MDMyNzd9.pKZLRRdShykZ_4AbvciMOhueZhoubP7tEX6IflKhEkJue4LZNQ4JNNZEktN-y1veLXbf-PJOAdfndaa3CFvCeC8fvWjX7w-SLAPIXxxB38_O3u3LDPW1GDT_GcZszMth4OoMwmAkhfvya8u0sBoCUnvRONwXhn0wz_eBjudTG0kPqcnTt5COuHJFJvC2aMX5JkRQDb9UPgyLzYD3fAc6jZKrY3XA2vGO4XYuqeBOq57hJF9DN2s6jeQbuI3LwyhjfK_x1DzWLUig8eYNGUDoo9VlwyxXdQzxA6Iv4UIFQxR9X7yenFASvUwXgT-ytruYmxk-8-mF1_RDTTanqYOjfg",
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

    url = f"https://vitaa.digiicampus.com/api/programme/intake/{row['departmentId']}/{row['batchYear']}/update"

    print("Calling:", url)
    print(payload)

    response = requests.put(
        url,
        headers=headers,
        json=payload   # <-- important (not data=)
    )

    print("Status:", response.status_code)
    print("Response:", response.text)
    time.sleep(3)
    # Remove break if you want all combinations processed
    # break