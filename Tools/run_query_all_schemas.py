
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import mysql.connector
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_env import get_db_config, list_schemas

MAX_WORKERS = 8
CONNECT_TIMEOUT = 20
OUTPUT_DIR = Path.home() / "Downloads"
# Output column -> source column in the `college` table, appended in this order.
COLLEGE_COLUMNS = {
    "college": "college_name",
    "college_initials": "college_initials",
    "cp_url": "cp_url",
}


def read_query() -> str:
    """Read a (possibly multi-line) query; finish with ';' or a blank line."""
    print("Enter SQL query (end with ';' or an empty line):")
    lines = []
    while True:
        line = input()
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line)
        if line.rstrip().endswith(";"):
            break
    return "\n".join(lines).strip().rstrip(";").strip()


def run_on_schema(schema: str, query: str) -> pd.DataFrame:
    conn = mysql.connector.connect(**get_db_config(schema), connection_timeout=CONNECT_TIMEOUT)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM college")
        cols = cur.column_names
        college_rows = cur.fetchall()
        college_info = {}
        for out_col, src_col in COLLEGE_COLUMNS.items():
            values = [r[cols.index(src_col)] for r in college_rows if r[cols.index(src_col)]]
            college_info[out_col] = ", ".join(dict.fromkeys(str(v) for v in values))
        college_info["college"] = college_info["college"] or schema

        cur.execute(query)
        df = pd.DataFrame(cur.fetchall(), columns=cur.column_names)
        cur.close()
    finally:
        conn.close()

    for out_col, value in college_info.items():
        df[out_col] = value
    return df


def main():
    query = read_query()
    if not query:
        print("No query entered.")
        return

    schemas = list_schemas()
    print(f"\nRunning on {len(schemas)} schemas...\n")

    frames, failures = [], {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(run_on_schema, s, query): s for s in schemas}
        for i, fut in enumerate(as_completed(futures), 1):
            schema = futures[fut]
            try:
                df = fut.result()
                frames.append(df)
                print(f"[{i}/{len(schemas)}] {schema}: {len(df)} rows")
            except Exception as exc:
                failures[schema] = str(exc)
                print(f"[{i}/{len(schemas)}] {schema}: FAILED - {exc}")

    frames = [f for f in frames if not f.empty]
    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if "college" in result.columns:
        tail = list(COLLEGE_COLUMNS)
        result = result[[c for c in result.columns if c not in tail] + tail]

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"all_schemas_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    with pd.ExcelWriter(out_path) as writer:
        result.to_excel(writer, sheet_name="Result", index=False)
        if failures:
            pd.DataFrame(failures.items(), columns=["schema", "error"]).to_excel(
                writer, sheet_name="Failures", index=False
            )

    print(f"\nTotal rows: {len(result)} | Failed schemas: {len(failures)}")
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
