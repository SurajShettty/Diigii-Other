import os
import pandas as pd
from sqlalchemy import create_engine, text
import warnings

warnings.filterwarnings("ignore")

# =========================================================
# DATABASE CONFIGURATION  (fill in your creds)
# =========================================================
USERNAME = "suraj_shetty"
PASSWORD = "pTXr8yJmOR"
HOST = "collpolldb11-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com"
PORT = "3306"
DATABASE = "collpoll_kce"

# =========================================================
# OUTPUT
# =========================================================
# One Excel file per course code, named {course_code}_{term_id}.xlsx
OUTPUT_TEMPLATE = r"C:\Users\suraj\OneDrive\Desktop\KCE Assessment\{course_code}_{term_id}.xlsx"

# =========================================================
# CREATE DB CONNECTION
# =========================================================
engine = create_engine(
    f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}",
    pool_pre_ping=True,
    pool_recycle=1800,
)
print("Database connection established.")

# =========================================================
# INPUT
# =========================================================
course_codes_raw = input("Enter course code(s), comma-separated (e.g. 23adr405,23adr406): ").strip()
term_id = input("Enter term_id (e.g. 6): ").strip()

course_codes = [c.strip() for c in course_codes_raw.split(",") if c.strip()]

# =========================================================
# QUERY  (parameterised by course_code + term_id)
# =========================================================
QUERY = text("""
    SELECT student_ukid,
           registration_id,
           CONCAT(ua.f_name, ' ', ua.l_name) AS student_name,
           COALESCE(cv.course_code, cv.course_code) AS course_code,
           COALESCE(cv.course_name, cv.course_name) AS course_name,
           cct.name AS course_component,
           t.name  AS term,
           ca.name AS assessment_name,
           cam.marks
    FROM class_assessment_marks cam
    LEFT JOIN user_attributes ua       ON ua.ukid = cam.student_ukid
    LEFT JOIN class_assessment ca      ON ca.id = cam.assessment_id
    LEFT JOIN class c                  ON c.id = ca.class_id
    LEFT JOIN term_course tc           ON tc.course_id = c.course_id AND tc.term_id = c.term_id
    LEFT JOIN course_version cv        ON cv.id = tc.course_version_id
    LEFT JOIN course cc                ON cc.course_id = cv.course_id
    LEFT JOIN term t                   ON t.id = tc.term_id
    LEFT JOIN course_component_type cct ON cct.id = c.course_component_type_id
    WHERE tc.term_id = :term_id
      AND COALESCE(cv.course_code, cv.course_code) = :course_code
      AND cct.id = 1
    GROUP BY class_id, student_ukid, ca.id
""")

index_cols = [
    "student_ukid",
    "registration_id",
    "student_name",
    "course_code",
    "course_name",
    "course_component",
    "term",
]


def build_pivot(course_code):
    """Fetch + pivot a single course. Returns the pivoted DataFrame (empty if no rows)."""
    df = pd.read_sql(QUERY, engine, params={"term_id": term_id, "course_code": course_code})
    print(f"  {course_code}: fetched {len(df)} rows")
    if df.empty:
        return df

    cols = [col for col in index_cols if col in df.columns]
    df["marks"] = pd.to_numeric(df["marks"], errors="coerce")

    pivoted = df.pivot_table(
        index=cols,
        columns="assessment_name",
        values="marks",
        aggfunc="first",   # use "max"/"mean" if a student has duplicate assessment rows
    ).reset_index()
    pivoted.columns.name = None
    return pivoted


def safe_filename(name):
    """Strip characters Windows forbids in filenames."""
    for ch in r':\/?*[]<>|"':
        name = name.replace(ch, "_")
    return name

# =========================================================
# WRITE OUTPUT  (one Excel file per course code)
# =========================================================
os.makedirs(os.path.dirname(OUTPUT_TEMPLATE), exist_ok=True)

for course_code in course_codes:
    pivoted = build_pivot(course_code)
    if pivoted.empty:
        print(f"  {course_code}: no rows — skipped")
        continue

    output_path = OUTPUT_TEMPLATE.format(
        course_code=safe_filename(course_code), term_id=safe_filename(term_id)
    )
    pivoted.to_excel(output_path, index=False, engine="openpyxl")
    print(f"  {course_code}: wrote {len(pivoted)} rows -> {output_path}")

print("\nDone.")
