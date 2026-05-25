import pandas as pd
import requests
import json
import math
import time
from datetime import datetime

# =========================
# CONFIG
# =========================
INPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\excepption template.xlsx"
OUTPUT_FILE =r"C:\Users\suraj\OneDrive\Desktop\excepption output.xlsx"

URL = "https://gims.digiicampus.com/api/attendance/exception"

HEADERS = {
    "Content-Type": "application/json",
    "auth-token": "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzEwMTIzNzEiLCJ1a2lkIjoxMDEyMzcxLCJ1c2VyVHlwZSI6ImNvbGxwb2xsLWFkbWluIiwiaW50ZWdyYXRpb25Sb2xlcyI6W10sImludGVncmF0aW9uRmVhdHVyZUZsYWdzIjpbXSwiaHViTmFtZSI6Imh1Yi1hcC1zb3V0aC0xLWRiMyIsInRlbmFudE5hbWUiOiJnaW1zIiwiaW5zdGl0dXRlVXJsIjoiaHR0cHM6Ly9naW1zLmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6NDEyLCJqdGkiOiI5YmU0ODM5NS0zMGU0LTQ0ZmEtYTU1Yy0zMzlmN2FmZGE4NjEiLCJpYXQiOjE3NzQ2MjQ0NTcsImV4cCI6MTc3NTI0OTA1N30.jObON7JzLaFBbNJqrvLd3PkZeTb8vi3YCjWoanMMHES-7ZNZPbuAfjA2s06iBUtjN1Vmd-qB17mS3OA42r1dxh6ymeKTBwo-CjHnhFSl-4IboXTqrjUNS81vfLizs0j8SEvIWQP379m99Cf4agzu07wP8sufc6tEJ_3s29Ehar6nKpDV1i5K-baxTdXxleiV9APEenzlQ4MhoezdQtqz8UnlWDC2NG3LKvvPHSZAguHjPTcnQYv10amZk_PiWEdkWpJueyER7zly8AMB4O7O61c6yVKMZKGN4He8VyFNvGkjumSwNa8FtV94cEC5R5CCw2tqMG7VMbsXYXrkr4AliA"   # replace with real token
}

# =========================
# HELPER FUNCTIONS
# =========================
def parse_bool(value):
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in ["true", "1", "yes"]:
        return True
    return False

def parse_ukids(value):
    return [int(x.strip()) for x in str(value).split(",")]

def safe_int(val):
    return int(val) if pd.notna(val) else None

def safe_str(val):
    return str(val).strip() if pd.notna(val) else ""

def safe_bool(val):
    if pd.isna(val):
        return False
    return str(val).strip().lower() in ["true", "1", "yes"]

def safe_date(val):
    if pd.isna(val):
        return ""
    return pd.to_datetime(val).strftime("%Y-%m-%d")

def safe_time(val):
    if pd.isna(val):
        return ""
    return pd.to_datetime(val).strftime("%H:%M:%S")

# def parse_ukids(val):
#     return [int(x.strip()) for x in str(val).split(",")]

def main():
    try:
        df = pd.read_excel(INPUT_FILE)
    except Exception as e:
        print(f" Error reading Excel file: {e}")
        return

    results = []

    for index, row in df.iterrows():
        try:
            payload = {
                "ukids": parse_ukids(row["ukid"]),
                "performedByUkid": int(row["performedByUkid"]),
                "statusId": str(row["statusId"]),
                "startDate": str(row["startDate"]).split(" ")[0],
                "endDate": str(row["endDate"]).split(" ")[0],
                "isEntireDay": parse_bool(row["isEntireDay"]),
                "startTime": str(row["startTime"]),
                "endTime": str(row["endTime"]),
                "termId": int(row["termId"]),
                  "remark": None,
                "attachments": [],
                "commonAttachment": False
            }

            response = requests.post(
                URL,
                headers=HEADERS,
                data=json.dumps(payload),
                timeout=30
            )

            status = "SUCCESS" if response.status_code == 200 else "FAILED"

            print(f"Row {index+1}: {status}")

            results.append({
                "row": index + 1,
                "ukid": row["ukid"],
                "status_code": response.status_code,
                "status": status,
                "response": response.text
            })

        except Exception as e:
            print(f"Row {index+1}: ERROR - {e}")

            results.append({
                "row": index + 1,
                "ukid": row.get("ukid", ""),
                "status_code": "ERROR",
                "status": "FAILED",
                "response": str(e)
            })
        finally:
            time.sleep(5)

    try:
        result_df = pd.DataFrame(results)
        result_df.to_excel(OUTPUT_FILE, index=False)
        print(f"\n Results saved to {OUTPUT_FILE}")
    except Exception as e:
        print(f" Error saving results: {e}")

if __name__ == "__main__":
    print(" Script started at:", datetime.now())
    main()
    print(" Script finished at:", datetime.now())
