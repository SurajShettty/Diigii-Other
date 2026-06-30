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
import time
import requests
import pandas as pd

# ---------------- CONFIG ----------------
INPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\run.xlsx"   # CSV or Excel with the termCourseIds
COLUMN     = "term_course_id"          # column holding the ids
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzE2ODIxMjQiLCJ1a2lkIjoxNjgyMTI0LCJ1c2VyVHlwZSI6ImZhY3VsdHkiLCJpbnRlZ3JhdGlvblJvbGVzIjpbXSwiaW50ZWdyYXRpb25GZWF0dXJlRmxhZ3MiOlsiRElHSUlfQUlfQ0hBVEJPVCJdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtZGI5IiwidGVuYW50TmFtZSI6ImlpbG1ndXJ1Z3JhbSIsImluc3RpdHV0ZVVybCI6Imh0dHBzOi8vaWlsbWd1cnVncmFtLmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6NTczLCJqdGkiOiJhMjVjN2Q1NC04MGE0LTRlMzEtYjU5Ni02NmJmMWVlNmFjMGYiLCJpYXQiOjE3ODIyMTUyMTksImV4cCI6MTc4MjgzOTgxOX0.CRbnN9l3javuIzvZpE8pyq3gtNprvZCFNaJlIiaPcPWKI7W99xGc2JClFY3QMPWv5h4U-2AEZ2mv1q0G-Itdj-c33ABmOhTm9gQwZlQTozqkXxd9d2zsANGY7FPFjx5ANNSBe8ZOJxaU9W8VMclryGFNkHqtdmANco4OsaSJr4gzyXzLQ8AZN-heSACUY0XoQnWxix_DDtzsp-LuxkUXwDc5ESOFt9EmOwZ01nLgeh29xdkggoBgz7-YIpD__Tn1YZF9HuspfClX3s_TqogRLtAAHsx8foptiJRZFDyI0vgCIENUZNlDFYgJxxa6IHLqrXLiSumCxcIn4fsmuIIYEw"
OUTPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\result_log.xlsx"
BASE_URL = "https://iilmgurugram.digiicampus.com/api/ems/courseResult/result/{}"
# BASE_URL = "https://iilmgurugram.digiicampus.com/rest/bulkDataProcess/abort/{}?reason=1"
# ----------------------------------------


def read_ids(path, column):
    # Detect the real format by content, not the file extension:
    # a real .xlsx is a zip and starts with "PK"; anything else we treat as CSV.
    with open(path, "rb") as f:
        is_real_xlsx = f.read(2) == b"PK"
    if is_real_xlsx:
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

        time.sleep(3)

    pd.DataFrame(log).to_excel(OUTPUT_FILE, index=False)
    print(f"\nDone. Log written to {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()
