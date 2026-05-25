"""
Generate course-wise answer sheet reports from assessment data.

Usage:
  python course_wise_answer_sheet_report.py

The script prompts for assessment_schedule_id(s) and term id(s) at runtime
(comma-separated when you need more than one).

Edit the DB_* placeholders below with your database credentials before running.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import pymysql


# Database placeholders - update these before running.
DB_HOST = "collpolldb11-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com"
DB_USER = "suraj_shetty"
DB_PASSWORD = "pTXr8yJmOR"
DB_NAME = "collpoll_kahe"
DB_PORT = 3306
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "KAHE Answer Sheets"


def _parse_comma_separated_ints(raw: str, label: str) -> list[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError(f"Please provide at least one {label}.")
    return [int(p) for p in parts]


def parse_assessment_schedule_ids(raw: str) -> list[int]:
    return _parse_comma_separated_ints(raw, "assessment_schedule_id")


def parse_term_ids(raw: str) -> list[int]:
    return _parse_comma_separated_ints(raw, "term id")


def sanitize_filename(value: str) -> str:
    # Keep names safe for Windows file system.
    safe = re.sub(r'[<>:"/\\|?*]', "_", str(value).strip())
    safe = re.sub(r"\s+", " ", safe).strip(" .")
    return safe or "course"


def prompt_assessment_schedule_ids() -> list[int]:
    while True:
        raw = input(
            "Enter assessment_schedule_id(s), comma-separated if multiple "
            "(e.g. 49 or 48,49): "
        ).strip()
        try:
            return parse_assessment_schedule_ids(raw)
        except ValueError as exc:
            print(exc)


def prompt_term_ids() -> list[int]:
    while True:
        raw = input(
            "Enter term id(s), comma-separated if multiple (e.g. 6 or 6,7,8): "
        ).strip()
        try:
            return parse_term_ids(raw)
        except ValueError as exc:
            print(exc)


def build_query(assessment_schedule_ids_count: int, term_ids_count: int) -> str:
    schedule_ph = ",".join(["%s"] * assessment_schedule_ids_count)
    term_ph = ",".join(["%s"] * term_ids_count)
    return f"""
        SELECT
            tc.id AS term_course_id,
            tc.term_id,
            t.name AS term_name,
            ua.registration_id,
            eaas.answer_sheet_number,
            co.course_code,
            co.course_name
        FROM ems_assessment ea
        INNER JOIN term_course tc
            ON tc.id = ea.term_course_id
        INNER JOIN course co
            ON tc.course_id = co.course_id
        INNER JOIN term t
            ON t.id = tc.term_id
        INNER JOIN ems_assessment_question_paper eaqp
            ON ea.id = eaqp.assessment_id
        INNER JOIN ems_assessment_answer_sheet eaas
            ON eaas.question_paper_id = eaqp.id
        INNER JOIN user_attributes ua
            ON ua.ukid = eaas.examinee_ukid
        WHERE ea.assessment_schedule_id IN ({schedule_ph})
          AND tc.term_id IN ({term_ph}) 
    """


def fetch_report_data(
    connection: pymysql.connections.Connection,
    assessment_schedule_ids: list[int],
    term_ids: list[int],
) -> pd.DataFrame:
    sql = build_query(len(assessment_schedule_ids), len(term_ids))
    params = [*assessment_schedule_ids, *term_ids]
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        time.sleep(5)
        rows = cursor.fetchall()
    return pd.DataFrame(rows)


def write_course_files(df: pd.DataFrame, output_dir: Path) -> list[Path]:
    if df.empty:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    required_cols = [
        "term_course_id",
        "term_id",
        "term_name",
        "registration_id",
        "answer_sheet_number",
        "course_code",
        "course_name",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = pd.NA

    written_files: list[Path] = []

    # One file per term_course (tc.id). Grouping only by course_name/course_code merges
    # sections and cross-term offerings that share the same catalogue course.
    for term_course_id, group_df in df.groupby("term_course_id", dropna=False):
        course_code = group_df["course_code"].iloc[0]
        base = sanitize_filename(course_code if pd.notna(course_code) else "course")
        # term_course_id keeps filenames unique when the same course title appears twice.
        if pd.isna(term_course_id):
            tcid_str = "unknown"
        else:
            tcid_str = str(int(float(term_course_id)))
        file_name = f"{base}_{tcid_str}.xlsx"

        out_path = output_dir / file_name
        out_df = group_df[["term_name", "registration_id", "answer_sheet_number", "course_code"]].copy()
        out_df.columns = ["Term Name", "Registration ID", "Answer Sheet Number", "Course Code"]
        out_df.to_excel(out_path, index=False, engine="openpyxl")
        written_files.append(out_path)

    return written_files


def main() -> None:
    assessment_schedule_ids = prompt_assessment_schedule_ids()
    term_ids = prompt_term_ids()
    output_dir = DEFAULT_OUTPUT_DIR

    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        df = fetch_report_data(
            connection=connection,
            assessment_schedule_ids=assessment_schedule_ids,
            term_ids=term_ids,
        )
    finally:
        connection.close()

    files = write_course_files(df, output_dir)
    if not files:
        print("No rows found for provided filters. No files generated.")
        return

    print(f"Generated {len(files)} file(s) in: {output_dir}")
    print(
        "(Each file is one term_course_id with at least one answer sheet for the "
        "selected assessment schedule(s); courses with no matching rows are omitted.)"
    )
    for file_path in files:
        print(f" - {file_path}")


if __name__ == "__main__":
    main()
