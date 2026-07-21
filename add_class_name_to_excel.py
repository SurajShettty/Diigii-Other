"""Add class name (batch) next to class id in every Excel file in a folder.

Workflow:
1. Ask for the folder containing Excel files.
2. Ask for the DB schema (from db_credentials.json) to query against.
3. Fetch id -> batch mapping from the `class` table.
4. For each Excel file, add a new column "class_name" immediately after the
   column containing class ids and populate it with the corresponding batch.

Usage:
    python add_class_name_to_excel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pymysql

from db_env import get_db_config, list_schemas

DB_QUERY = "SELECT id, batch FROM class"

# Column name variations that might hold the class id.
CLASS_ID_ALIASES = [
    "class id*",
    "class id",
    "class_id",
    "classid",
    "class id.",
    "class_id.",
    "id",
]


def prompt_for_schema() -> str:
    """Show available schemas and ask the user to pick one."""
    schemas = list_schemas()
    print("Available DB schemas:")
    for idx, schema in enumerate(schemas, 1):
        print(f"  {idx}. {schema}")
    print()

    while True:
        choice = input("Enter schema name (or the number from the list): ").strip()
        if not choice:
            print("Please enter a schema name.")
            continue
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(schemas):
                return schemas[idx - 1]
            print(f"Number must be between 1 and {len(schemas)}.")
            continue
        try:
            get_db_config(choice)
            return choice
        except KeyError as exc:
            print(exc)


def fetch_class_mapping(schema: str) -> dict:
    """Return a dict mapping class id -> batch name."""
    cfg = get_db_config(schema)
    conn = pymysql.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(DB_QUERY)
            rows = cur.fetchall()
    finally:
        conn.close()
    return {row["id"]: row["batch"] for row in rows if row["id"] is not None}


def find_class_id_column(df: pd.DataFrame) -> str | None:
    """Return the first column header that looks like a class id column."""
    lower_map = {str(col).strip().lower(): str(col) for col in df.columns}
    for alias in CLASS_ID_ALIASES:
        if alias in lower_map:
            return lower_map[alias]
    return None


def process_excel_file(path: Path, class_map: dict) -> bool:
    """Read an Excel file, add class_name next to class_id, and save it."""
    print(f"Processing: {path}")
    try:
        df = pd.read_excel(path)
    except Exception as exc:
        print(f"  Could not read {path}: {exc}")
        return False

    if df.empty:
        print(f"  Skipping empty file: {path}")
        return False

    class_id_col = find_class_id_column(df)
    if class_id_col is None:
        print(f"  No class id column found in {path}")
        return False

    class_id_pos = list(df.columns).index(class_id_col)

    def resolve_class_name(value):
        """Convert a class id value to its batch name, handling NaN etc."""
        if pd.isna(value):
            return None
        try:
            # Values may be numeric (float/int) or string.
            class_id = int(value) if float(value).is_integer() else float(value)
        except (ValueError, TypeError):
            class_id = str(value).strip()
        return class_map.get(class_id)

    class_name_values = df[class_id_col].apply(resolve_class_name)

    # Insert a new "class_name" column right after the class_id column.
    new_col_name = "class_name"
    if new_col_name in df.columns:
        # Avoid duplicate column name; append a counter if necessary.
        counter = 2
        while f"{new_col_name}_{counter}" in df.columns:
            counter += 1
        new_col_name = f"{new_col_name}_{counter}"

    df.insert(class_id_pos + 1, new_col_name, class_name_values)

    try:
        df.to_excel(path, index=False)
    except Exception as exc:
        print(f"  Could not save {path}: {exc}")
        return False

    print(f"  Added '{new_col_name}' after '{class_id_col}' -> {len(df)} rows")
    return True


def main() -> None:
    folder = input("Enter the folder path containing Excel files: ").strip()
    folder_path = Path(folder).expanduser().resolve()
    if not folder_path.is_dir():
        print(f"Not a valid directory: {folder_path}")
        sys.exit(1)

    schema = prompt_for_schema()
    print(f"\nUsing schema: {schema}")

    class_map = fetch_class_mapping(schema)
    print(f"Fetched {len(class_map)} class mappings from DB.\n")

    excel_files = sorted(
        f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in (".xlsx", ".xls")
    )
    if not excel_files:
        print(f"No Excel files found in {folder_path}")
        sys.exit(1)

    processed = 0
    for excel_file in excel_files:
        if process_excel_file(excel_file, class_map):
            processed += 1

    print(f"\nDone. {processed}/{len(excel_files)} files updated.")


if __name__ == "__main__":
    main()
