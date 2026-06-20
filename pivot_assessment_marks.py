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
# {course_code} and {term_id} get filled in from your input below.
OUTPUT_TEMPLATE = r"C:\Users\suraj\OneDrive\Desktop\{course_code}_term{term_id}_pivoted.csv"

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
course_code = input("Enter course code (e.g. 23adr405): ").strip()
term_id = input("Enter term_id (e.g. 6): ").strip()

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

df = pd.read_sql(QUERY, engine, params={"term_id": term_id, "course_code": course_code})
print(f"Fetched {len(df)} rows from DB.")

if df.empty:
    print("No rows returned — check the course_code / term_id.")
    raise SystemExit

# =========================================================
# PIVOT: assessment_name -> columns, marks -> values
# =========================================================
index_cols = [
    "student_ukid",
    "registration_id",
    "student_name",
    "course_code",
    "course_name",
    "course_component",
    "term",
]
index_cols = [col for col in index_cols if col in df.columns]

df["marks"] = pd.to_numeric(df["marks"], errors="coerce")

pivoted = df.pivot_table(
    index=index_cols,
    columns="assessment_name",
    values="marks",
    aggfunc="first",   # use "max"/"mean" if a student has duplicate assessment rows
).reset_index()
pivoted.columns.name = None

# =========================================================
# WRITE OUTPUT
# =========================================================
output_path = OUTPUT_TEMPLATE.format(course_code=course_code, term_id=term_id)
pivoted.to_csv(output_path, index=False)
print(f"Wrote {len(pivoted)} rows -> {output_path}")
print("Assessment columns:", [c for c in pivoted.columns if c not in index_cols])
