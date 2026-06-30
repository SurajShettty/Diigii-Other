"""
Loop termCourseId values through the courseResult API and write an Excel log.

API: GET https://demo.digiicampus.com/api/ems/courseResult/result/{termCourseId}
Headers: Auth-Token, Content-Type: application/json

Usage:
    python fetch_course_results.py

Edit the CONFIG section below: input file, Auth-Token, column name.
Input file (CSV or Excel) just needs a column of termCourseId values.
Output: result_log.xlsx
"""

import os
import requests
import pandas as pd

# ---------------- CONFIG ----------------
INPUT_FILE = "C:\\Users\\suraj\\OneDrive\\Desktop\\Book1IILMG Course Auto Evaluation List.xlsx"   # CSV or Excel with the termCourseIds
COLUMN     = "term_course_id"          # column holding the ids
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzM1ODg0IiwidWtpZCI6MzU4ODQsInVzZXJUeXBlIjoiY29sbHBvbGwtYWRtaW4iLCJpbnRlZ3JhdGlvblJvbGVzIjpbIkRDQiJdLCJpbnRlZ3JhdGlvbkZlYXR1cmVGbGFncyI6WyJESUdJSV9BSV9DSEFUQk9UIl0sImh1Yk5hbWUiOiJodWItYXAtc291dGgtMS1jb21tb24taHViIiwidGVuYW50TmFtZSI6ImRlbW8iLCJpbnN0aXR1dGVVcmwiOiJodHRwczovL2RlbW8uZGlnaWljYW1wdXMuY29tIiwiY29sbGVnZUlkIjozOSwianRpIjoiYjJmNDc0NzktOTZjZS00MTFkLWJjZTctYmMwZGFmMTQxZTY5IiwiaWF0IjoxNzgyNzQ0NDc0LCJleHAiOjE3ODMzNjkwNzR9.HBnBxUpV-xlDpxRKlnYp1RvXP44lW9ngO9tZGOKeNfvEQ2fqRMbfQMzsDuvigyv7Vx591mKZQwiF9Y4O2D2KeJm-Rqg6uvZ9rkZJjeVeUZG_oKR7yZ67ORfZ6Py4VW9uSI_iidYZ7oyAvNPtql_4w4aNGID-eydXHwkDjZ1-KqnXL2vVmBHWUI1S-BZX8iNfcOJzvRu8Ct2jjU9ehVW1l_8FhFup5EabcdTKscEYdsv8nE0Q0JTm5ErGo226q23C99veWtbo1Q8UjMiE4rEGjY5jfNO6eB0u43wRlNwfiqq4O02h4TIAE7qOEw2l8vdkv8K20WgXgaktEetXmqtq-w"
OUTPUT_FILE = "C:\\Users\\suraj\\OneDrive\\Desktop\\result_log.xlsx"
BASE_URL = "https://demo.digiicampus.com/api/ems/courseResult/result/{}"
# ----------------------------------------


def read_ids(path, column):
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str)
    if column not in df.columns:
        column = df.columns[0]
    return [str(v).strip() for v in df[column] if str(v).strip() and str(v).lower() != "nan"]


def main():
    headers = {"Auth-Token": AUTH_TOKEN, "Content-Type": "application/json"}
    ids = read_ids(INPUT_FILE, COLUMN)
    print(f"Found {len(ids)} termCourseIds. Starting...\n")

    log = []
    for i, tcid in enumerate(ids, start=1):
        try:
            resp = requests.put(BASE_URL.format(tcid), headers=headers, timeout=30)
            status = "SUCCESS" if resp.ok else "FAILED"
            print(f"[{i}/{len(ids)}] {tcid} -> HTTP {resp.status_code} {status}")
            log.append({
                "termCourseId": tcid,
                "httpStatus": resp.status_code,
                "result": status,
                "response": resp.text[:1000],
            })
        except requests.RequestException as exc:
            print(f"[{i}/{len(ids)}] {tcid} -> ERROR: {exc}")
            log.append({
                "termCourseId": tcid,
                "httpStatus": "",
                "result": "ERROR",
                "response": str(exc),
            })

    pd.DataFrame(log).to_excel(OUTPUT_FILE, index=False)
    print(f"\nDone. Log written to {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()
