import time
import traceback

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import warnings

warnings.filterwarnings("ignore")

# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DB_TYPE = "mysql"  # mysql or postgresql

USERNAME = "suraj_shetty"
PASSWORD = "CsQwi1mggE"
HOST = "collpolldb8-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com"
PORT = "3306"
DATABASE = "collpoll_iihmr"

# SCHEMA_NAME = "your_schema"

# =========================================================
# INPUT
# =========================================================

# Comma-separated list of term IDs. Whitespace around commas is fine.
TERM_IDS = "18,19,20,21,28,29,30,31,32,33,34,35,36,37,38,39,44,45,54,55,56,57,58,59,60,61,62,63,64,65,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,125,126,127,128,129,130,131,132,133,134,135"

# Seconds to sleep between term runs (reduces DB load on a read replica).
DELAY_BETWEEN_TERMS_SECONDS = 10

# =========================================================
# OUTPUT
# =========================================================

OUTPUT_DIR = r"C:\Users\suraj\OneDrive\Desktop\IIHMRJ_Student_Course_Assessment_Marks_Reports"
OUTPUT_FILE_TEMPLATE = (
    OUTPUT_DIR + r"\student_course_assessment_marks_report_{term_id}.csv"
)

# =========================================================
# CREATE DB CONNECTION
# =========================================================

if DB_TYPE.lower() == "mysql":
    connection_string = (
        f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"
    )

elif DB_TYPE.lower() == "postgresql":
    connection_string = (
        f"postgresql+psycopg2://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}"
    )

else:
    raise ValueError("Unsupported DB_TYPE")

# pool_pre_ping recycles stale connections; pool_recycle keeps long loops safe.
engine = create_engine(
    connection_string,
    pool_pre_ping=True,
    pool_recycle=1800,
)

print("Database connection established.")

# =========================================================
# HELPERS
# =========================================================

def sql_in_clause(values):
    """Build a safe SQL IN clause from an iterable of values.

    Handles the single-element case (Python's (x,) repr is invalid SQL)
    and the empty case (() is invalid SQL — substitute a sentinel that
    matches nothing).
    """
    cleaned = [v for v in values if v is not None and not pd.isna(v)]
    if not cleaned:
        return "(NULL)"
    rendered = []
    for v in cleaned:
        if isinstance(v, (int, np.integer)):
            rendered.append(str(int(v)))
        elif isinstance(v, float) and float(v).is_integer():
            rendered.append(str(int(v)))
        elif isinstance(v, (float, np.floating)):
            rendered.append(repr(float(v)))
        else:
            escaped = str(v).replace("'", "''")
            rendered.append(f"'{escaped}'")
    return "(" + ",".join(rendered) + ")"


def parse_term_ids(raw):
    """Parse 'a, b, c' into a list of ints, ignoring blanks and duplicates."""
    seen = set()
    out = []
    for chunk in str(raw).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        term_id = int(chunk)
        if term_id in seen:
            continue
        seen.add(term_id)
        out.append(term_id)
    return out


# =========================================================
# PER-TERM PIPELINE
# =========================================================

def run_for_term(term_id):
    """Build the marks report CSV for a single term."""

    output_file = OUTPUT_FILE_TEMPLATE.format(term_id=term_id)

    # ---- QUERY 1 : ESP DATA ----
    esp_query = f"""
    SELECT
        esp.id AS esp_id,
        esp.ukid AS student_ukid,
        esp.exam_type_id,
        esp.exam_id,
        t.id AS term_id,
        t.name AS term_name,
        ee.name AS exam,
        eet.id AS exam_type_id_eet,
        esc.student_programme_enrollment_id,
        esc.term_course_id,
        esc.id AS esc_id,

        eescg.grade,
        eescg.grade_point,
        eescg.moderation_grade,
        eescg.moderation_grade_point,
        eescg.enrollment_status,
        eescg.attendance_status,
        eescg.fairness_status,
        eescg.consider_for_sgpa_calculation,
        eescg.is_failed,
        eescg.remark,

        eescg.moderation_marks AS course_moderated_marks,
        eescg.marks AS course_marks,
        eescg.re_exam_marks

    FROM ems_student_programme_enrollment esp

    INNER JOIN ems_examination ee
        ON ee.id = esp.exam_id

    INNER JOIN term t
        ON t.id = ee.term_id

    LEFT JOIN ems_examination_type eet
        ON eet.id = esp.exam_type_id

    INNER JOIN ems_student_course_enrollment esc
        ON esp.id = esc.student_programme_enrollment_id

    LEFT JOIN ems_examination_student_course_grade eescg
        ON eescg.student_ukid = esp.ukid
        AND eescg.term_course_id = esc.term_course_id

    WHERE t.id = {term_id}
    """

    print(f"[term {term_id}] Running ESP query...")
    esp_df = pd.read_sql(esp_query, engine)

    if esp_df.empty:
        print(f"[term {term_id}] No data found. Skipping.")
        return None

    print(f"[term {term_id}] ESP rows fetched: {len(esp_df)}")

    exam_ids = esp_df['exam_id'].dropna().unique().tolist()
    exam_type_ids = esp_df['exam_type_id'].dropna().unique().tolist()
    student_ukids = esp_df['student_ukid'].dropna().unique().tolist()

    # ---- QUERY 2 : COURSE DETAILS ----
    esc_query = f"""
    SELECT
        tc.id AS term_course_id,
        c.course_id,
        c.course_name,
        co.course_code,
        c.course_credits,
        d.department_name AS course_department_name

    FROM term_course tc

    INNER JOIN course_version c
        ON c.id = tc.course_version_id

    LEFT JOIN course co
        ON co.course_id = c.course_id

    LEFT JOIN department d
        ON d.department_id = co.department_id

    WHERE tc.term_id = {term_id}
    """

    print(f"[term {term_id}] Running Course query...")
    esc_df = pd.read_sql(esc_query, engine)
    print(f"[term {term_id}] Course rows fetched: {len(esc_df)}")

    course_id_list = esc_df['course_id'].dropna().unique().tolist()

    # ---- QUERY 3 : EXAM SCHEMA ----
    eesch_query = f"""
    SELECT
        eesch.course_id,
        eesch.examination_id AS exam_id,
        eesch.examination_schema_id,
        eesch.grade_schema_id,

        gs.name AS grade_schema,

        es.name AS evaluation_schema,
        es.total_marks,

        eescon.examination_type_id AS exam_type_id,
        eescon.schema_component_id,
        eescon.exam_type_label AS assessment_name,
        eescon.maximum_marks AS assessment_maximum_marks,
        eescon.weightage AS composition_weightage,
        eescon.passing_marks,

        eescot.weightage AS component_weightage,

        eect.name AS component_name,
        eect.type AS component_type

    FROM ems_examination_course_schema eesch

    LEFT JOIN grade_schema gs
        ON eesch.grade_schema_id = gs.id

    LEFT JOIN ems_examination_schema es
        ON es.id = eesch.examination_schema_id

    LEFT JOIN ems_examination_schema_composition eescon
        ON eescon.examination_schema_id = eesch.examination_schema_id

    LEFT JOIN ems_examination_schema_component eescot
        ON eescon.schema_component_id = eescot.id

    LEFT JOIN ems_examination_component_type eect
        ON eect.id = eescot.component_type_id

    WHERE eesch.course_id IN {sql_in_clause(course_id_list)}
    AND eesch.examination_id IN {sql_in_clause(exam_ids)}
    """

    print(f"[term {term_id}] Running Schema query...")
    eesch_eescon_df = pd.read_sql(eesch_query, engine)
    print(f"[term {term_id}] Schema rows fetched: {len(eesch_eescon_df)}")

    # ---- QUERY 4 : STUDENT MARKS ----
    eesm_query = f"""
    SELECT
        eesm.student_ukid,
        eesm.term_course_id,
        eesm.enrollment_id AS esc_id,

        eesm.marks AS assessment_effective_obtained_marks,

        eesm.revaluation_marks AS assessment_re_evalution_marks,

        eesm.moderation_marks AS assesment_moderated_marks

    FROM ems_examination_student_marks eesm

    WHERE eesm.student_ukid IN {sql_in_clause(student_ukids)}
    """

    print(f"[term {term_id}] Running Student Marks query...")
    eesm_df = pd.read_sql(eesm_query, engine)
    print(f"[term {term_id}] Student marks rows fetched: {len(eesm_df)}")

    # ---- QUERY 5 : COMPONENT MARKS ----
    schema_component_ids = (
        eesch_eescon_df['schema_component_id']
        .dropna()
        .unique()
        .tolist()
    )

    eesc_query = f"""
    SELECT
        eesc.student_ukid,
        eesc.term_course_id,
        eesc.schema_component_id,
        eesc.marks AS component_marks

    FROM ems_examination_student_component_marks eesc

    WHERE eesc.student_ukid IN {sql_in_clause(student_ukids)}
    AND eesc.schema_component_id IN {sql_in_clause(schema_component_ids)}
    """

    print(f"[term {term_id}] Running Component Marks query...")
    eesc_df = pd.read_sql(eesc_query, engine)
    print(f"[term {term_id}] Component marks rows fetched: {len(eesc_df)}")

    # ---- QUERY 6 : ANSWER SHEET ----
    ea_query = f"""
    SELECT
        ea.term_course_id,
        ea.exam_type_id,

        eaas.examinee_ukid AS student_ukid,

        eaas.answer_sheet_number

    FROM ems_assessment ea

    LEFT JOIN ems_assessment_question_paper eaqp
        ON eaqp.assessment_id = ea.id

    LEFT JOIN ems_assessment_answer_sheet eaas
        ON eaas.question_paper_id = eaqp.id

    WHERE ea.exam_type_id IN {sql_in_clause(exam_type_ids)}
    """

    print(f"[term {term_id}] Running Answer Sheet query...")
    ea_df = pd.read_sql(ea_query, engine)
    print(f"[term {term_id}] Answer sheet rows fetched: {len(ea_df)}")

    # ---- QUERY 7 : STUDENT DETAILS ----
    student_query = f"""
    SELECT
        ua.ukid AS student_ukid,
        CONCAT(ua.f_name, ' ', ua.l_name) AS student_name,
        ua.registration_id,
        sp.year_of_joining,
        p.programme_name,
        d.department_name

    FROM user_attributes ua

    LEFT JOIN student_profile sp
        ON sp.ukid = ua.ukid

    LEFT JOIN programme p
        ON p.programme_id = sp.programme_id

    LEFT JOIN department d
        ON d.department_id = p.department_id

    WHERE ua.user_type = 'student'
    AND ua.ukid IN {sql_in_clause(student_ukids)}
    """

    print(f"[term {term_id}] Running Student Details query...")
    student_df = pd.read_sql(student_query, engine)
    print(f"[term {term_id}] Student detail rows fetched: {len(student_df)}")

    # ---- MERGE ----
    print(f"[term {term_id}] Merging dataframes...")

    df = esp_df.copy()
    df = df.merge(esc_df, on='term_course_id', how='left')
    df = df.merge(
        eesch_eescon_df,
        on=['course_id', 'exam_id', 'exam_type_id'],
        how='left',
    )
    df = df.merge(
        eesm_df,
        on=['student_ukid', 'term_course_id', 'esc_id'],
        how='left',
    )
    df = df.merge(
        eesc_df,
        on=['student_ukid', 'term_course_id', 'schema_component_id'],
        how='left',
    )
    df = df.merge(
        ea_df,
        on=['student_ukid', 'term_course_id', 'exam_type_id'],
        how='left',
    )
    df = df.merge(
        student_df,
        on='student_ukid',
        how='left',
    )

    print(f"[term {term_id}] Merged rows: {len(df)}")

    # ---- CALCULATIONS ----
    print(f"[term {term_id}] Applying calculations...")

    # MySQL DECIMAL columns come back as Python Decimal objects in
    # object-dtype Series. np.round / arithmetic on object dtype raises
    # "loop of ufunc does not support argument 0 of type float which has
    # no callable rint method". Coerce numerics to float up front.
    numeric_cols = [
        'component_weightage',
        'total_marks',
        'assessment_maximum_marks',
        'composition_weightage',
        'assessment_effective_obtained_marks',
        'assessment_re_evalution_marks',
        'assesment_moderated_marks',
        'passing_marks',
        'component_marks',
        'course_marks',
        'course_moderated_marks',
        're_exam_marks',
        'grade_point',
        'moderation_grade_point',
        'course_credits',
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    df['component_maximum_marks'] = np.where(
        df['component_type'].isin(['RE_EXAM', 'MAKEUP']),
        np.nan,
        np.round(df['component_weightage'] * df['total_marks'] / 100, 2),
    )

    df['assessment_effective_marks'] = np.round(
        df['assessment_maximum_marks'] * df['composition_weightage'] / 100,
        2,
    )

    df['assessment_total_marks'] = np.where(
        df['component_type'] == 'CUSTOM',
        df['component_marks'],
        np.where(
            df['component_type'] == 'MAKEUP',
            df['assessment_effective_obtained_marks'],
            np.where(
                df['component_type'].isna(),
                df['assessment_effective_obtained_marks'],
                np.where(
                    df['component_type'] == 'RE_EXAM',
                    df['assessment_re_evalution_marks'],
                    df['component_marks'],
                ),
            ),
        ),
    )

    df['course_moderation_total_marks'] = np.where(
        df['component_type'] == 'RE_EXAM',
        df['re_exam_marks'],
        df['course_marks'],
    )

    df['assessment_effective_weightage_obtained_marks'] = np.round(
        df['assessment_effective_obtained_marks']
        * df['composition_weightage']
        / 100,
        2,
    )

    df['weightage_applying_passing_marks'] = np.round(
        df['passing_marks'] * df['composition_weightage'] / 100,
        2,
    )

    df['component_weightage'] = np.round(df['component_weightage'], 2)

    df = df.drop_duplicates()
    print(f"[term {term_id}] Rows after deduplication: {len(df)}")

    final_columns = [
        "term_id",
        "term_name",
        "term_course_id",
        "exam",
        "grade_schema",
        "evaluation_schema",
        "course_id",
        "course_name",
        "course_code",
        "course_credits",
        "course_department_name",
        "student_ukid",
        "student_name",
        "registration_id",
        "year_of_joining",
        "programme_name",
        "department_name",
        "answer_sheet_number",
        "component_name",
        "component_maximum_marks",
        "assessment_name",
        "assessment_maximum_marks",
        "assessment_effective_marks",
        "assessment_effective_obtained_marks",
        "assessment_re_evalution_marks",
        "assesment_moderated_marks",
        "assessment_total_marks",
        "course_moderated_marks",
        "course_moderation_total_marks",
        "grade",
        "grade_point",
        "moderation_grade",
        "moderation_grade_point",
        "enrollment_status",
        "attendance_status",
        "fairness_status",
        "consider_for_sgpa_calculation",
        "is_failed",
        "remark",
        "assessment_effective_weightage_obtained_marks",
        "composition_weightage",
        "weightage_applying_passing_marks",
        "passing_marks",
        "component_weightage",
    ]

    final_df = df[final_columns].copy()

    text_columns = [
        'moderation_grade',
        'remark',
        'answer_sheet_number',
        'grade',
        'enrollment_status',
        'attendance_status',
        'fairness_status',
        'grade_schema',
    ]

    for col in text_columns:
        if col in final_df.columns:
            final_df[col] = final_df[col].fillna('')

    print(f"[term {term_id}] Writing CSV: {output_file}")
    final_df.to_csv(
        output_file,
        index=False,
        encoding='utf-8-sig',
    )

    return {
        "term_id": term_id,
        "rows": len(final_df),
        "file": output_file,
    }


# =========================================================
# DRIVER LOOP
# =========================================================

term_ids = parse_term_ids(TERM_IDS)
print(f"Total terms to process: {len(term_ids)}")
print(f"Delay between terms   : {DELAY_BETWEEN_TERMS_SECONDS}s")

results = []
failures = []

for index, term_id in enumerate(term_ids, start=1):
    print("=" * 60)
    print(f"[{index}/{len(term_ids)}] TERM_ID = {term_id}")
    print("=" * 60)

    try:
        result = run_for_term(term_id)
        if result is not None:
            results.append(result)
    except Exception as exc:
        print(f"[term {term_id}] FAILED: {exc}")
        traceback.print_exc()
        failures.append({"term_id": term_id, "error": str(exc)})

    # Sleep between terms, but not after the last one.
    if index < len(term_ids):
        print(f"Sleeping {DELAY_BETWEEN_TERMS_SECONDS}s before next term...")
        time.sleep(DELAY_BETWEEN_TERMS_SECONDS)

print("=" * 60)
print("REPORT GENERATION COMPLETE")
print(f"Succeeded : {len(results)}")
print(f"Skipped/Failed : {len(term_ids) - len(results)}")
for r in results:
    print(f"  term {r['term_id']:>6} : {r['rows']:>7} rows -> {r['file']}")
for f in failures:
    print(f"  term {f['term_id']:>6} : ERROR -> {f['error']}")
print("=" * 60)
