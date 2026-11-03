"""
Bulk-delete EMS exam assessments on Digiicampus.

Endpoint: DELETE https://ace.digiicampus.com/api/emsExam/assessments/{assessment_id}

Usage:
    Set AUTH_TOKEN and INPUT_FILE below (or use the DIGII_AUTH_TOKEN env var for the token).
    python delete_assessments.py                  # deletes IDs in INPUT_FILE (asks for confirmation)
    python delete_assessments.py ids.csv          # optional: override INPUT_FILE from the command line

Input file: a .csv with a column named 'assessment_id', or a .txt with one ID per line.
Output:     delete_log.csv with one row per ID (status, HTTP code, response, timestamp).
            Re-running skips IDs already logged as 'deleted', so it is safe to resume.
"""

import csv
import os
import sys
import time
from datetime import datetime

import requests

BASE_URL = "https://ace.digiicampus.com/api/emsExam/assessments/{assessment_id}"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzE3MDYzNjMiLCJ1a2lkIjoxNzA2MzYzLCJ1c2VyVHlwZSI6ImZhY3VsdHkiLCJpbnRlZ3JhdGlvblJvbGVzIjpbXSwiaW50ZWdyYXRpb25GZWF0dXJlRmxhZ3MiOlsiRElHSUlfQUlfQ0hBVEJPVCJdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtZGI5IiwidGVuYW50TmFtZSI6ImFjZSIsImluc3RpdHV0ZVVybCI6Imh0dHBzOi8vYWNlLmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6NTc5LCJqdGkiOiIwZDhmMzVkMi00MWVlLTRlOWMtYmQwYS1hYjM2OTJhZjI1YTAiLCJpYXQiOjE3OTMzNTAzMzcsImV4cCI6MTc5Mzk3NDkzN30.Z2dZGx7p4Bd5AbADjXho3GaOloN94Sp1ns9iicSR1imIPb2djHBS8nASyUwr3OtlZ-HQ1dyMHw4go20qL3YWrzNVBnuK7o5gIVox6Klwpjq06xqwGOeAXj7KItqwsWwevMTjrK3IwwnMLYaj3sxMm5DrXNwaxQ-lA96FMVd5BtIc3_fyuVl2SYtMrhAAq-ktNHI_QJQdaUVbfNu7rWAiPJ8lHS_O9XfEm4X0uKopfKBeWfjultqxs-8kVs_Leei6Qr1tYsD9rnm--I6s5Vevf-tM4NbfU9v1uug5cp9swmUAAE32MLMrzf9pbiPjw-ISkpPntMZluw_HGPWacPOcuQ"  # paste token here; falls back to DIGII_AUTH_TOKEN env var if left empty
INPUT_FILE = "C:\\Users\\suraj\\OneDrive\\Desktop\\assessment_ids.csv"  # .csv with 'assessment_id' column, or .txt
LOG_FILE = "C:\\Users\\suraj\\OneDrive\\Desktop\\delete_log.csv"
DELAY_SECONDS = 5       # pause after every call
MAX_RETRIES = 3          # retries on 429 / 5xx / network errors
TIMEOUT = 30
REQUEST_BODY = ["FULL"]  # JSON body sent with every DELETE


def load_ids(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        if path.lower().endswith(".csv"):
            reader = csv.DictReader(f)
            if "assessment_id" not in (reader.fieldnames or []):
                sys.exit("CSV must have a column named 'assessment_id'")
            ids = [row["assessment_id"].strip() for row in reader]
        else:
            ids = [line.strip() for line in f]
    ids = [i for i in ids if i]
    return list(dict.fromkeys(ids))  # de-duplicate, keep order


def already_deleted():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, newline="", encoding="utf-8") as f:
        return {r["assessment_id"] for r in csv.DictReader(f) if r["status"] == "deleted"}


def log_result(row):
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["assessment_id", "status", "http_code", "response", "timestamp"]
        )
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def delete_one(session, assessment_id):
    url = BASE_URL.format(assessment_id=assessment_id)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.delete(url, json=REQUEST_BODY, timeout=TIMEOUT)
        except requests.RequestException as e:
            if attempt == MAX_RETRIES:
                return "error", "", str(e)[:300]
            time.sleep(2 ** attempt)
            continue

        if resp.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
            time.sleep(2 ** attempt)
            continue

        body = resp.text[:300].replace("\n", " ")
        if 200 <= resp.status_code < 300:
            return "deleted", resp.status_code, body
        if resp.status_code == 404:
            return "not_found", resp.status_code, body
        if resp.status_code in (401, 403):
            return "auth_failed", resp.status_code, body
        return "failed", resp.status_code, body
    return "failed", "", "max retries reached"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE
    if not os.path.exists(path):
        sys.exit(f"Input file not found: {path}")

    token = AUTH_TOKEN or os.environ.get("DIGII_AUTH_TOKEN")
    if not token:
        sys.exit("Set AUTH_TOKEN in the script (or the DIGII_AUTH_TOKEN environment variable) first.")

    ids = load_ids(path)
    done = already_deleted()
    todo = [i for i in ids if i not in done]
    print(f"{len(ids)} IDs in file, {len(done & set(ids))} already deleted, {len(todo)} to process.")

    if input(f"\nType DELETE to permanently delete {len(todo)} assessments: ") != "DELETE":
        sys.exit("Aborted.")

    session = requests.Session()
    session.headers.update({"Auth-Token": token, "Content-Type": "application/json"})

    counts = {}
    for n, aid in enumerate(todo, 1):
        status, code, body = delete_one(session, aid)
        counts[status] = counts.get(status, 0) + 1
        log_result({
            "assessment_id": aid, "status": status, "http_code": code,
            "response": body, "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        print(f"[{n}/{len(todo)}] {aid}: {status} ({code})")

        if status == "auth_failed":
            print("Auth failed - token is probably invalid or expired. Stopping.")
            break
        time.sleep(DELAY_SECONDS)

    print("\nSummary:", counts, f"\nLog written to {LOG_FILE}")


if __name__ == "__main__":
    main()