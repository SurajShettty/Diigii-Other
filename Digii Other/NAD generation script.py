import pandas as pd
import numpy as np
from num2words import num2words
import re
import logging
import warnings
from pathlib import Path
from datetime import datetime
import pymysql

warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CREDENTIALS (embedded — no external helper / .env dependency)
# ============================================================================

DB_CONFIG = {
    "host": "collpolldb19-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    "user": "suraj_shetty",
    "password": "LW3J0MU3mZ",
    "database": "collpoll_mujbl",
}

# Alternate tenant DB (uncomment / edit as needed):
# DB_CONFIG = {
#     "host": "digiidb3-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
#     "user": "suraj_shetty",
#     "password": "AdaQwNaEPo",
#     "database": "collpoll_cu",
# }


def connect_to_tenant_database(tenant_name):
    """Connect to the tenant database using the embedded credentials above."""
    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
    )

# ============================================================================
# EMBEDDED SQL QUERIES - EXAM DATA (SPLIT INTO 2 QUERIES)
# ============================================================================

# Query 1: Exam Details (with examination_schema_id for joining)
QUERY_1_EXAM_DATA = """
SELECT
    t.name as term_name,
    espe.ukid as student_ukid,
    coalesce(c.course_code,cv.course_code) course_code,
    CAST(
        (
            (CAST(t.acad_year_start AS SIGNED) - CAST(sp.year_of_joining AS SIGNED)) * 
            CASE
                WHEN p.system = 'semester' THEN 2
                WHEN p.system = 'trimester' THEN 3
                ELSE 1
            END
        ) + CAST(t.sequence AS SIGNED)
        AS SIGNED
    ) as sem_year_no,
    (CAST(t.acad_year_start AS SIGNED) - CAST(sp.year_of_joining AS SIGNED) + 1) AS year_of_study,
    t.acad_year_start AS acad_year_start,
    t.acad_year_end AS acad_year_end,
    pt.name AS programme_type,
    p.system,
    coalesce(c.course_name,cv.course_name) course_name,
    cv.course_credits  course_credits,
    eesc.marks,
    eesc.re_exam_marks as re_exam_ku_marks,
    CASE WHEN (eesc.is_failed) >= 1 THEN 'FAIL' ELSE 'PASS' END is_failed,
    eesc.grade,
    eesc.re_exam_grade as re_exam_ku_grade,
    eesc.grade_point,
    eesc.re_exam_grade_point as re_exam_ku_grade_point,
    (eesc.grade_point * cv.course_credits) AS credit_points,
    (eesc.re_exam_grade_point * cv.course_credits) AS re_exam_ku_credit_points,
    tc.id AS term_course_id,
    ecs.examination_schema_id
FROM
    ems_student_programme_enrollment espe
INNER JOIN ems_student_course_enrollment esce 
    ON espe.id = esce.student_programme_enrollment_id
INNER JOIN ems_examination ee
    ON ee.id = espe.exam_id 
INNER JOIN term_course tc
    ON tc.id = esce.term_course_id
    left join course_version cv on cv.id = tc.course_version_id
    left join course c on c.course_id = cv.course_id
INNER JOIN student_profile sp
    ON sp.ukid = espe.ukid
INNER JOIN programme p
    ON p.programme_id = sp.programme_id
LEFT JOIN programme_types pt
    ON pt.id = p.programme_type_id
INNER JOIN term t
    ON t.id = ee.term_id
INNER JOIN ems_examination_student_course_grade eesc
    ON eesc.term_course_id = tc.id AND eesc.student_ukid = espe.ukid
INNER JOIN ems_examination_course_schema ecs 
    ON ecs.examination_id = ee.id AND ecs.course_id = tc.course_id
WHERE
    t.id IN ({TERM_IDS}) 
    AND esce.enrollment_status != 'NOT_ENROLLED'
GROUP BY eesc.student_ukid, tc.course_name, t.name,tc.id
"""

# Query 2: Schema Component Weights (to be processed in Python)
QUERY_2_SCHEMA_WEIGHTS = """
SELECT
    examination_schema_id,
    eect.name AS label,
    SUM((eescon.weightage * maximum_marks) / 100) AS max_weightage,
    SUM((eescon.weightage * minimum_marks) / 100) AS min_weightage
FROM ems_examination_schema_composition eescon
LEFT JOIN ems_examination_schema_component eescot ON eescon.schema_component_id = eescot.id
LEFT JOIN ems_examination_component_type eect ON eect.id = eescot.component_type_id
GROUP BY examination_schema_id, eect.name
"""

# Subjectwise Internal / External marks (per student, per term_course) — the actual
# component marks scored, summed under the 'Internal' / 'External' component types.
QUERY_SUBJECTWISE_INT_EXT = """
SELECT
    eesm.student_ukid,
    eesm.term_course_id,
    eect.name AS label,
    SUM(eesm.marks) AS marks
FROM ems_examination_student_marks eesm
INNER JOIN ems_examination_schema_composition eescon ON eescon.id = eesm.exam_schema_composition_id
INNER JOIN ems_examination_schema_component eescot ON eescot.id = eescon.schema_component_id
INNER JOIN ems_examination_component_type eect ON eect.id = eescot.component_type_id
INNER JOIN term_course tc ON tc.id = eesm.term_course_id
WHERE tc.term_id IN ({TERM_IDS})
    AND eect.name IN ('Internal', 'External')
GROUP BY eesm.student_ukid, eesm.term_course_id, eect.name
"""

QUERY_2_CGPA = """
SELECT 
    exam_id,
    student_ukid,
    COALESCE(re_exam_cgpa, cgpa) AS cgpa,
    ROW_NUMBER() OVER (PARTITION BY exam_id, student_ukid ORDER BY id DESC) AS rn
FROM ems_examination_student_cgpa
WHERE exam_id IN (
    SELECT DISTINCT esp.exam_id
    FROM ems_student_programme_enrollment esp
    INNER JOIN ems_examination ee ON ee.id = esp.exam_id
    INNER JOIN term t ON t.id = ee.term_id
    WHERE t.id IN ({TERM_IDS})
)
"""

QUERY_3_SGPA = """
SELECT 
    exam_id,
    student_ukid,
    COALESCE(re_exam_sgpa, sgpa) AS sgpa,
    ROW_NUMBER() OVER (PARTITION BY exam_id, student_ukid ORDER BY id DESC) AS rn
FROM ems_examination_student_sgpa
WHERE exam_id IN (
    SELECT DISTINCT esp.exam_id
    FROM ems_student_programme_enrollment esp
    INNER JOIN ems_examination ee ON ee.id = esp.exam_id
    INNER JOIN term t ON t.id = ee.term_id
    WHERE t.id IN ({TERM_IDS})
)
"""

# ============================================================================
# USER DETAILS QUERIES (SPLIT INTO MULTIPLE QUERIES)
# ============================================================================

# Query 1: User Details Master Fields
QUERY_USER_DETAILS_MASTER = """
SELECT
    t1.ukid,
    MAX(CASE WHEN t2.identifier = 'MOTHER_NAME' THEN t1.value END) AS mother_name,
    MAX(CASE WHEN t2.identifier = 'MOTHER_FIRST_NAME' THEN t1.value END) AS mother_first_name,
    MAX(CASE WHEN t2.identifier = 'MOTHER_MIDDLE_NAME' THEN t1.value END) AS mother_middle_name,
    MAX(CASE WHEN t2.identifier = 'MOTHER_LAST_NAME' THEN t1.value END) AS mother_last_name,
    MAX(CASE WHEN t2.identifier = 'FATHER_NAME' THEN t1.value END) AS father_name,
    MAX(CASE WHEN t2.identifier = 'FATHER_FIRST_NAME' THEN t1.value END) AS father_first_name,
    MAX(CASE WHEN t2.identifier = 'FATHER_MIDDLE_NAME' THEN t1.value END) AS father_middle_name,
    MAX(CASE WHEN t2.identifier = 'FATHER_LAST_NAME' THEN t1.value END) AS father_last_name,
    MAX(CASE WHEN t2.identifier = 'GUARDIAN_NAME' THEN t1.value END) AS guardian_name,
    MAX(CASE WHEN t2.identifier = 'GUARDIAN_FIRST_NAME' THEN t1.value END) AS guardian_first_name,
    MAX(CASE WHEN t2.identifier = 'GUARDIAN_MIDDLE_NAME' THEN t1.value END) AS guardian_middle_name,
    MAX(CASE WHEN t2.identifier = 'GUARDIAN_LAST_NAME' THEN t1.value END) AS guardian_last_name,
    MAX(CASE WHEN t2.identifier = 'UNIVERSITY_ROLL_NUMBER' THEN t1.value END) AS university_roll_number,
    MAX(CASE WHEN t2.identifier = 'CERTIFICATE_NAME' THEN t1.value END) AS aadhar_name,
    MAX(CASE WHEN t2.identifier = 'DATE_OF_BIRTH' THEN t1.value END) AS dob,
    MAX(CASE WHEN t2.identifier = 'ACADEMIC_BANK_OF_CREDIT_ID' THEN t1.value END) AS abc_id,
    MAX(CASE WHEN t2.identifier = 'CASTE' THEN t1.value END) AS C,
    MAX(CASE WHEN t2.identifier = 'RELIGION' THEN t1.value END) AS Re,
    MAX(CASE WHEN t2.identifier = 'NATIONALITY' THEN t1.value END) AS Nat,
    MAX(CASE WHEN t2.identifier = 'PERMANENT_ADDRESS' THEN t1.value END) AS pt
FROM
    user_details_master_field_value t1
LEFT JOIN user_details_master_field t2 ON
    t1.field_id = t2.id
WHERE
    t2.identifier IN (
        'FATHER_NAME', 'FATHER_FIRST_NAME', 'FATHER_MIDDLE_NAME', 'FATHER_LAST_NAME',
        'GUARDIAN_NAME', 'GUARDIAN_FIRST_NAME', 'GUARDIAN_MIDDLE_NAME', 'GUARDIAN_LAST_NAME',
        'FATHERS_TITLE', 'MOTHERS_TITLE',
        'MOTHER_NAME', 'MOTHER_FIRST_NAME', 'MOTHER_MIDDLE_NAME', 'MOTHER_LAST_NAME',
        'UNIVERSITY_ROLL_NUMBER', 'CERTIFICATE_NAME', 'DATE_OF_BIRTH', 'ACADEMIC_BANK_OF_CREDIT_ID',
        'CASTE', 'RELIGION', 'NATIONALITY', 'PERMANENT_ADDRESS'
    )
    AND t1.ukid IN ({UKIDS})
GROUP BY
    t1.ukid
"""

# Query 2: User Attributes
QUERY_USER_ATTRIBUTES = """
SELECT
    ua.ukid,
    c.college_name as ORG_NAME,
    c.address as ORG_ADDRESS,
    c.city AS ORG_CITY,
    c.state_name AS ORG_STATE,
    c.pincode AS ORG_PIN,
    p.programme_name AS COURSE_NAME,
    sp.year_of_joining AS ADMISSION_YEAR,
    d.department_name AS DEPARTMENT,
    ua.registration_id AS REGN_NO,
    sp.application_number AS APPLICATION_NUMBER,
    CONCAT_WS(' ', ua.f_name, ua.m_name, ua.l_name) AS CNAME,
    CASE 
        WHEN sp.gender = 'male' THEN 'M'
        WHEN sp.gender = 'Female' THEN 'F'
        WHEN sp.gender = 'Transgender' THEN 'T'
        WHEN sp.gender = ' Not Available' THEN 'X'
    END AS GENDER,
    a.phone AS MOBILE,
    a.EMAIL,
    null AS ORG_CODE,
    null AS ORG_NAME_L,
    p.programme_code AS ACADEMIC_COURSE_ID,
    null AS COURSE_NAME_L,
    null AS COURSE_SUBTITLE,
    null AS INTR_COURSE_NAME_FIRST,
    null AS INTR_COURSE_NAME_SECOND,
    null AS STREAM,
    null AS STREAM_L,
    null AS STREAM_SECOND,
    null AS STREAM_SECOND_L,
    null AS PHOTO,
    'O' AS MRKS_REC_STATUS
FROM
    user_attributes ua
INNER JOIN authenticator a ON a.ukid = ua.ukid
INNER JOIN student_profile sp ON sp.ukid = ua.ukid
INNER JOIN programme p ON p.programme_id = sp.programme_id
INNER JOIN department d ON d.department_id = p.department_id 
INNER JOIN college c ON c.college_id = d.college_id
WHERE ua.ukid IN ({UKIDS})
"""

# Query 3: Specialisations
# The student's primary specialisation may be recorded under any of MAJOR /
# SPECIALISATION / CONCENTRATION / HONOUR depending on how the programme is set up
# (most use 'SPECIALISATION', not 'MAJOR'), with MINOR as the secondary. We start from
# the student's actual records (programme_specialisation_student) and exclude soft-deleted
# mappings/specialisations.
QUERY_SPECIALISATIONS = """
SELECT
    t2.ukid,
    MAX(CASE WHEN t1.specialisation_type = 'MAJOR' THEN t3.name END) AS major,
    MAX(CASE WHEN t1.specialisation_type = 'SPECIALISATION' THEN t3.name END) AS specialisation,
    MAX(CASE WHEN t1.specialisation_type = 'CONCENTRATION' THEN t3.name END) AS concentration,
    MAX(CASE WHEN t1.specialisation_type = 'HONOUR' THEN t3.name END) AS honour,
    MAX(CASE WHEN t1.specialisation_type = 'MINOR' THEN t3.name END) AS minor
FROM programme_specialisation_student t2
INNER JOIN programme_specialisation_mapping t1 ON t1.id = t2.programme_specialisation_mapping_id
LEFT JOIN specialisation t3 ON t1.specialisation_id = t3.id
WHERE t2.ukid IN ({UKIDS})
    AND t1.is_deleted = 0
    AND (t3.is_deleted = 0 OR t3.is_deleted IS NULL)
GROUP BY t2.ukid
"""

# Query 4: Blood Group and PH Status (tenant-specific field IDs)
def get_blood_ph_query(tenant_name, ukids_str):
    """Get blood group and PH query with tenant-specific field IDs"""
    # KU uses different field IDs
    if tenant_name.upper() == 'KU' or tenant_name.upper() == 'KISHKINDAUNIVERSITY':
        blood_field_id = 44
        ph_field_id = 149
    else:
        blood_field_id = 82
        ph_field_id = 182
    
    return f"""
SELECT 
    ukid,
    MAX(CASE WHEN field_id = {blood_field_id} THEN value_name END) AS blood_group_value,
    MAX(CASE WHEN field_id = {ph_field_id} THEN value_name END) AS ph_value
FROM (
    SELECT 
        t1.ukid,
        t1.field_id,
        COALESCE(t2.name, t1.value) AS value_name
    FROM user_details_master_field_value t1
    LEFT JOIN user_details_master_field_list_item t2 
        ON CAST(t2.id AS CHAR) = t1.value 
        AND t2.field_id = t1.field_id
    WHERE t1.field_id IN ({blood_field_id}, {ph_field_id})
        AND t1.ukid IN ({ukids_str})
        AND t1.value IS NOT NULL
) AS combined
GROUP BY ukid
"""

# ============================================================================
# QUERY EXECUTION FUNCTIONS
# ============================================================================

def _term_ids_sql(term_ids):
    """Render a list of term IDs as a SQL IN-list, e.g. [1, 2, 3] -> '1,2,3'."""
    return ','.join(str(int(t)) for t in term_ids)


def fetch_exam_data(conn, term_ids, is_re_exam=False):
    """Fetch exam data for all given term IDs in a single query and process in Python"""
    logger.info(f"Fetching {'re-exam' if is_re_exam else 'normal'} exam data for term_ids: {term_ids}")

    # Query 1: Fetch exam details (all terms at once to minimise DB round-trips)
    query1 = QUERY_1_EXAM_DATA.replace('{TERM_IDS}', _term_ids_sql(term_ids))
    cursor = conn.cursor()
    cursor.execute(query1)
    columns1 = [desc[0] for desc in cursor.description]
    rows1 = cursor.fetchall()
    df_exam = pd.DataFrame(rows1, columns=columns1)
    logger.info(f"  Fetched {len(df_exam)} exam records")
    
    if df_exam.empty:
        cursor.close()
        return df_exam
    
    # Query 2: Fetch schema weights
    cursor.execute(QUERY_2_SCHEMA_WEIGHTS)
    columns2 = [desc[0] for desc in cursor.description]
    rows2 = cursor.fetchall()
    df_schema = pd.DataFrame(rows2, columns=columns2)
    cursor.close()
    logger.info(f"  Fetched {len(df_schema)} schema weight records")
    
    # Process Query 2 in Python to calculate max/min marks
    # This matches the original SQL logic:
    # 1. Query 2 already groups by examination_schema_id, label and sums weightages
    # 2. Now we group by examination_schema_id and use MAX for max_weightage, MIN for min_weightage per label
    #    This matches: MAX(CASE WHEN label = 'Internal' THEN max_weightage END) AS max_internal_marks
    
    # First ensure we have summed values per (examination_schema_id, label) - query already does this, but be safe
    schema_summed = df_schema.groupby(['examination_schema_id', 'label']).agg({
        'max_weightage': 'sum',
        'min_weightage': 'sum'
    }).reset_index()
    
    # Now pivot to get columns for each label, using MAX for max_weightage and MIN for min_weightage
    # This matches the outer query logic: MAX(CASE WHEN label = 'Internal' THEN max_weightage END)
    schema_pivot_max = schema_summed.pivot_table(
        index='examination_schema_id',
        columns='label',
        values='max_weightage',
        aggfunc='max',  # MAX as per original query
        fill_value=0
    ).reset_index()
    
    schema_pivot_min = schema_summed.pivot_table(
        index='examination_schema_id',
        columns='label',
        values='min_weightage',
        aggfunc='min',  # MIN as per original query
        fill_value=0
    ).reset_index()
    
    # Merge the two pivots
    schema_pivot = schema_pivot_max.merge(
        schema_pivot_min,
        on='examination_schema_id',
        suffixes=('', '_min')
    )
    
    # Extract Internal/External or Internals/Externals values
    # Try Internal/External first (normal exam), then Internals/Externals (re-exam)
    if 'Internal' in schema_pivot.columns:
        schema_pivot['max_internal_marks'] = schema_pivot['Internal'].fillna(0)
        schema_pivot['max_external_marks'] = schema_pivot.get('External', pd.Series([0] * len(schema_pivot))).fillna(0)
        schema_pivot['min_internal_marks'] = schema_pivot.get('Internal_min', pd.Series([0] * len(schema_pivot))).fillna(0)
        schema_pivot['min_external_marks'] = schema_pivot.get('External_min', pd.Series([0] * len(schema_pivot))).fillna(0)
    elif 'Internals' in schema_pivot.columns:
        schema_pivot['max_internal_marks'] = schema_pivot['Internals'].fillna(0)
        schema_pivot['max_external_marks'] = schema_pivot.get('Externals', pd.Series([0] * len(schema_pivot))).fillna(0)
        schema_pivot['min_internal_marks'] = schema_pivot.get('Internals_min', pd.Series([0] * len(schema_pivot))).fillna(0)
        schema_pivot['min_external_marks'] = schema_pivot.get('Externals_min', pd.Series([0] * len(schema_pivot))).fillna(0)
    else:
        # Default to 0 if no matching columns found
        schema_pivot['max_internal_marks'] = 0
        schema_pivot['max_external_marks'] = 0
        schema_pivot['min_internal_marks'] = 0
        schema_pivot['min_external_marks'] = 0
    
    # Merge with exam data
    df_exam = df_exam.merge(
        schema_pivot[['examination_schema_id', 'max_internal_marks', 'max_external_marks', 
                     'min_internal_marks', 'min_external_marks']],
        on='examination_schema_id',
        how='left'
    )
    
    # Calculate maximum_marks and minimum_marks
    # This matches: COALESCE(ees.max_internal_marks, 0) + COALESCE(ees.max_external_marks, 0) AS maximum_marks
    df_exam['maximum_marks'] = (
        df_exam['max_internal_marks'].fillna(0) + 
        df_exam['max_external_marks'].fillna(0)
    )
    # This matches: COALESCE(ees.min_external_marks, 0) + COALESCE(ees.min_internal_marks, 0) AS minimum_marks
    df_exam['minimum_marks'] = (
        df_exam['min_external_marks'].fillna(0) + 
        df_exam['min_internal_marks'].fillna(0)
    )
    
    # Handle re-exam data based on user input
    if is_re_exam:
        # Use re_exam fields (re_exam_ku_marks, etc. from query)
        if 're_exam_ku_marks' in df_exam.columns:
            df_exam['marks'] = df_exam['re_exam_ku_marks'].fillna(df_exam['marks'])
            df_exam['grade'] = df_exam.get('re_exam_ku_grade', df_exam['grade'])
            df_exam['grade_point'] = df_exam.get('re_exam_ku_grade_point', df_exam['grade_point'])
            df_exam['credit_points'] = df_exam.get('re_exam_ku_credit_points', df_exam['credit_points'])
            # Filter for records with re_exam data
            df_exam = df_exam[df_exam['re_exam_ku_marks'].notna()]
        else:
            logger.warning("Re-exam mode selected but no re-exam data found in query results")
    
    # Drop intermediate columns
    df_exam = df_exam.drop(columns=[
        'examination_schema_id', 'max_internal_marks', 'max_external_marks',
        'min_internal_marks', 'min_external_marks', 're_exam_ku_marks',
        're_exam_ku_grade', 're_exam_ku_grade_point', 're_exam_ku_credit_points'
    ], errors='ignore')
    
    return df_exam

def fetch_cgpa_data(conn, term_ids):
    """Fetch CGPA data for all given term IDs"""
    logger.info("Fetching CGPA data...")
    query = QUERY_2_CGPA.replace('{TERM_IDS}', _term_ids_sql(term_ids))
    
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    
    df = pd.DataFrame(rows, columns=columns)
    # Filter to get only the latest record per student
    df = df[df['rn'] == 1].drop(columns=['rn'])
    logger.info(f"  Fetched {len(df)} CGPA records")
    return df

def fetch_sgpa_data(conn, term_ids):
    """Fetch SGPA data for all given term IDs"""
    logger.info("Fetching SGPA data...")
    query = QUERY_3_SGPA.replace('{TERM_IDS}', _term_ids_sql(term_ids))
    
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    
    df = pd.DataFrame(rows, columns=columns)
    # Filter to get only the latest record per student
    df = df[df['rn'] == 1].drop(columns=['rn'])
    logger.info(f"  Fetched {len(df)} SGPA records")
    return df


def fetch_subjectwise_int_ext(conn, term_ids):
    """Fetch subjectwise Internal / External marks and pivot to one row per
    (student_ukid, term_course_id) with 'Internal' and 'External' columns."""
    logger.info("Fetching subjectwise Internal/External marks...")
    query = QUERY_SUBJECTWISE_INT_EXT.replace('{TERM_IDS}', _term_ids_sql(term_ids))

    cursor = conn.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()

    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        logger.info("  No Internal/External component marks found")
        return pd.DataFrame(columns=['student_ukid', 'term_course_id', 'Internal', 'External'])

    pivot = df.pivot_table(
        index=['student_ukid', 'term_course_id'],
        columns='label', values='marks', aggfunc='sum'
    ).reset_index()
    for col in ('Internal', 'External'):
        if col not in pivot.columns:
            pivot[col] = np.nan
    logger.info(f"  Fetched Internal/External marks for {len(pivot)} (student, course) pairs")
    return pivot[['student_ukid', 'term_course_id', 'Internal', 'External']]


def fetch_user_details(conn, tenant_name, student_ukids):
    """Fetch user details using multiple queries and join in Python"""
    logger.info("Fetching user details...")
    
    if not student_ukids or len(student_ukids) == 0:
        logger.warning("No student UKIDs provided, returning empty DataFrame")
        return pd.DataFrame()
    
    ukids_str = ','.join([f"'{ukid}'" for ukid in student_ukids])
    
    # Query 1: User Details Master Fields
    query1 = QUERY_USER_DETAILS_MASTER.replace('{UKIDS}', ukids_str)
    cursor = conn.cursor()
    cursor.execute(query1)
    columns1 = [desc[0] for desc in cursor.description]
    rows1 = cursor.fetchall()
    df_master = pd.DataFrame(rows1, columns=columns1)
    logger.info(f"  Fetched {len(df_master)} user master field records")
    
    # Query 2: User Attributes
    query2 = QUERY_USER_ATTRIBUTES.replace('{UKIDS}', ukids_str)
    cursor.execute(query2)
    columns2 = [desc[0] for desc in cursor.description]
    rows2 = cursor.fetchall()
    df_attrs = pd.DataFrame(rows2, columns=columns2)
    logger.info(f"  Fetched {len(df_attrs)} user attribute records")
    
    # Query 3: Specialisations
    query3 = QUERY_SPECIALISATIONS.replace('{UKIDS}', ukids_str)
    cursor.execute(query3)
    columns3 = [desc[0] for desc in cursor.description]
    rows3 = cursor.fetchall()
    df_spec = pd.DataFrame(rows3, columns=columns3)
    logger.info(f"  Fetched {len(df_spec)} specialisation records")
    
    # Query 4: Blood Group and PH
    query4 = get_blood_ph_query(tenant_name, ukids_str)
    cursor.execute(query4)
    columns4 = [desc[0] for desc in cursor.description]
    rows4 = cursor.fetchall()
    df_blood_ph = pd.DataFrame(rows4, columns=columns4)
    cursor.close()
    logger.info(f"  Fetched {len(df_blood_ph)} blood/PH records")
    
    # Join all dataframes on ukid
    df_user = df_attrs.copy()
    
    # Merge master fields
    if not df_master.empty:
        # Process master fields to create final columns
        df_master['RROLL'] = df_master['university_roll_number']
        df_master['ABC_ACCOUNT_ID'] = df_master['abc_id']
        df_master['AADHAAR_NAME'] = df_master['aadhar_name']
        df_master['DOB'] = pd.to_datetime(df_master['dob'], errors='coerce').dt.strftime('%d/%m/%Y')
        df_master['CASTE'] = df_master['C']
        df_master['RELIGION'] = df_master['Re']
        df_master['NATIONALITY'] = df_master['Nat']
        df_master['FNAME'] = df_master.apply(
            lambda row: row['father_name'] if pd.notna(row['father_name']) 
            else ' '.join(filter(None, [row.get('father_first_name'), row.get('father_middle_name'), row.get('father_last_name')])),
            axis=1
        )
        df_master['MNAME'] = df_master.apply(
            lambda row: row['mother_name'] if pd.notna(row['mother_name'])
            else ' '.join(filter(None, [row.get('mother_first_name'), row.get('mother_middle_name'), row.get('mother_last_name')])),
            axis=1
        )
        df_master['GNAME'] = df_master.apply(
            lambda row: row['guardian_name'] if pd.notna(row['guardian_name'])
            else ' '.join(filter(None, [row.get('guardian_first_name'), row.get('guardian_middle_name'), row.get('guardian_last_name')])),
            axis=1
        )
        df_master['STUDENT_ADDRESS'] = df_master['pt']
        
        df_user = df_user.merge(
            df_master[['ukid', 'RROLL', 'ABC_ACCOUNT_ID', 'AADHAAR_NAME', 'DOB', 
                      'CASTE', 'RELIGION', 'NATIONALITY', 'FNAME', 'MNAME', 'GNAME', 'STUDENT_ADDRESS']],
            on='ukid',
            how='left'
        )
    
    # Merge specialisations
    if not df_spec.empty:
        # Primary specialisation = first available among MAJOR / SPECIALISATION /
        # CONCENTRATION / HONOUR (programmes use different type labels for it).
        df_spec['SPECIALIZATION_MAJOR'] = (
            df_spec['major']
            .fillna(df_spec['specialisation'])
            .fillna(df_spec['concentration'])
            .fillna(df_spec['honour'])
        )
        df_spec['SPECIALIZATION_MINOR'] = df_spec['minor']
        df_user = df_user.merge(
            df_spec[['ukid', 'SPECIALIZATION_MAJOR', 'SPECIALIZATION_MINOR']],
            on='ukid',
            how='left'
        )
    else:
        df_user['SPECIALIZATION_MAJOR'] = None
        df_user['SPECIALIZATION_MINOR'] = None

    # Stream maps to specialization: Major -> STREAM, Minor -> STREAM_SECOND.
    # NOTE: dual-specialization behaviour pending JSPM confirmation (see project notes).
    df_user['STREAM'] = df_user.get('SPECIALIZATION_MAJOR')
    df_user['STREAM_SECOND'] = df_user.get('SPECIALIZATION_MINOR')

    # Merge blood group and PH
    if not df_blood_ph.empty:
        # Get blood group name from list item
        df_blood_ph['BLOOD_GROUP'] = df_blood_ph['blood_group_value']
        df_blood_ph['PH'] = df_blood_ph['ph_value'].apply(
            lambda x: 'Y' if x == 'Yes' else 'N' if x == 'No' else None
        )
        df_user = df_user.merge(
            df_blood_ph[['ukid', 'BLOOD_GROUP', 'PH']],
            on='ukid',
            how='left'
        )
    else:
        df_user['BLOOD_GROUP'] = None
        df_user['PH'] = None
    
    # SESSION is the term's academic-year span and is set per term in create_course_records.

    # Rename ukid to student_ukid
    df_user.rename(columns={"ukid": "student_ukid"}, inplace=True)
    logger.info(f"  Merged {len(df_user)} user detail records")
    return df_user

# ============================================================================
# DATA PROCESSING FUNCTIONS
# ============================================================================

def merge_exam_data_with_schema(df_exam, df_cgpa, df_sgpa):
    """Merge exam data with CGPA and SGPA"""
    logger.info("Merging exam data with CGPA and SGPA...")
    
    # Merge CGPA and SGPA on student_ukid
    if not df_cgpa.empty:
        df_cgpa_unique = df_cgpa.groupby('student_ukid').first().reset_index()
        df_exam = df_exam.merge(df_cgpa_unique[['student_ukid', 'cgpa']], on='student_ukid', how='left')
    else:
        df_exam['cgpa'] = None
    
    if not df_sgpa.empty:
        df_sgpa_unique = df_sgpa.groupby('student_ukid').first().reset_index()
        df_exam = df_exam.merge(df_sgpa_unique[['student_ukid', 'sgpa']], on='student_ukid', how='left')
    else:
        df_exam['sgpa'] = None
    
    return df_exam

def process_course_data(df_exam):
    """Process course data - max/min marks are already in the query"""
    logger.info("Processing course data...")
    
    # Max/min marks are included in the query, just ensure they exist
    if 'maximum_marks' not in df_exam.columns:
        df_exam['maximum_marks'] = 0
    if 'minimum_marks' not in df_exam.columns:
        df_exam['minimum_marks'] = 0
    
    return df_exam

def classify_programme_type(programme_type):
    """Bucket a raw programme_type name into 'UG', 'PG', 'PHD', 'DIPLOMA',
    'CERTIFICATE' (or None if unknown).

    'diploma'/'certificate' are checked before pg/ug so a name like 'PG Diploma'
    is treated as a Diploma (UG-level by year), per client instruction.
    """
    if programme_type is None or (isinstance(programme_type, float) and pd.isna(programme_type)):
        return None
    p = str(programme_type).strip().lower()
    if not p:
        return None
    if 'phd' in p or 'ph.d' in p or 'doctora' in p:
        return 'PHD'
    if 'diploma' in p:
        return 'DIPLOMA'
    if 'certificate' in p or 'certification' in p:
        return 'CERTIFICATE'
    if p.startswith('pg') or 'post' in p or 'master' in p:
        return 'PG'
    if p.startswith('ug') or 'under' in p or 'bachelor' in p:
        return 'UG'
    return None


def compute_ncrf_level(programme_type, year_of_study):
    """Derive the NCrF level from programme type and the student's year of study.

    Mapping (per client-shared NCrF Table 3):
        UG / Diploma  1st/2nd/3rd/4th yr -> 4.5 / 5.0 / 5.5 / 6.0
        Certificate   (any year)         -> 4.5  (UG-Certificate)
        PG            1st/2nd yr         -> 6.5 / 7.0
        PhD           (any year)         -> 8.0
    Year of study is computed elsewhere as (acad_year_start - year_of_joining + 1),
    so a 2023 batch is in year 1 during AY 2023-24, year 2 in 2024-25, etc.
    """
    cat = classify_programme_type(programme_type)
    if cat is None:
        return None

    # Levels independent of year of study
    if cat == 'PHD':
        return 8.0
    if cat == 'CERTIFICATE':
        return 4.5

    if year_of_study is None or pd.isna(year_of_study):
        return None
    try:
        y = int(year_of_study)
    except (ValueError, TypeError):
        return None
    if y < 1:
        y = 1

    if cat in ('UG', 'DIPLOMA'):
        # 4th year (Honours / Research) and beyond cap at 6.0
        return {1: 4.5, 2: 5.0, 3: 5.5}.get(y, 6.0)
    if cat == 'PG':
        # 2nd year and beyond cap at 7.0
        return {1: 6.5}.get(y, 7.0)
    return None


def create_course_records(df_exam, df_int_ext=None):
    """Create course records in NAD format"""
    logger.info("Creating course records in NAD format...")

    df = df_exam.copy()

    # Bring in subjectwise Internal / External marks (per student, per term_course).
    if df_int_ext is not None and not df_int_ext.empty and 'term_course_id' in df.columns:
        df = df.merge(df_int_ext, on=['student_ukid', 'term_course_id'], how='left')
    else:
        df['Internal'] = np.nan
        df['External'] = np.nan

    df.sort_values(by=["student_ukid", "term_name", "sem_year_no", "course_code"], inplace=True)
    
    records = []
    max_courses = 0
    grouped = df.groupby(["student_ukid", "term_name", "sem_year_no"])
    
    for (ukid, term, sem), group in grouped:
        row = {
            "student_ukid": ukid,
            "term_name": term,
            "sem_year_no": sem
        }
        
        tot_max = tot_min = tot_marks = tot_grade_point = tot_credits = tot_credit_points = 0
        
        for i, (_, course) in enumerate(group.iterrows(), 1):
            # Internal / External bifurcation. When neither component is recorded for a
            # subject, fall back to putting the full marks under Internal and 0 External.
            internal_val = course.get('Internal')
            external_val = course.get('External')
            total_marks_val = course.get("marks", 0) if pd.notna(course.get("marks")) else 0
            if pd.isna(internal_val) and pd.isna(external_val):
                internal_val = total_marks_val
                external_val = 0

            row[f"SUB{i}NM"] = course["course_name"]
            row[f"SUB{i}"] = course["course_code"]
            row[f"SUB{i}MAX"] = course.get("maximum_marks", 0)
            row[f"SUB{i}MIN"] = course.get("minimum_marks", 0)
            row[f"SUB{i}_IntMarks"] = internal_val
            row[f"SUB{i}_ExtMarks"] = external_val
            row[f"SUB{i}_SESSION"] = ''
            row[f"SUB{i}_TH_MAX"] = ''
            row[f"SUB{i}_TH_MIN"] = ''
            row[f"SUB{i}_PR_MAX"] = ''
            row[f"SUB{i}_PR_MIN"] = ''
            row[f"SUB{i}_CE_MAX"] = ''
            row[f"SUB{i}_CE_MIN"] = ''
            row[f"SUB{i}_VV_MAX"] = ''
            row[f"SUB{i}_VV_MIN"] = ''
            row[f"SUB{i}_VV_GRADE"] = ''
            row[f"SUB{i}_TH_MRKS"] = ''
            row[f"SUB{i}_TH_CE_MAX"] = ''
            row[f"SUB{i}_TH_CE_MRKS"] = ''
            row[f"SUB{i}_TH_GRADE"] = ''
            row[f"SUB{i}_TH_AGGREGATE"] = ''
            row[f"SUB{i}_PR_AGGREGATE"] = ''
            row[f"SUB{i}_PR_MRKS"] = ''
            row[f"SUB{i}_PR_GRADE"] = ''
            row[f"SUB{i}_PR_CE_MAX"] = ''
            row[f"SUB{i}_PR_CE_MRKS"] = ''
            row[f"SUB{i}_PR_HOURS"] = ''
            row[f"SUB{i}_TH_HOURS"] = ''
            row[f"SUB{i}_TT_HOURS"] = ''
            row[f"SUB{i}_CE_WEIGHT_MRKS"] = ''
            row[f"SUB{i}_CE_MRKS"] = ''
            row[f"SUB{i}_CE_GRADE"] = ''
            row[f"SUB{i}_CE1_MRKS"] = ''
            row[f"SUB{i}_CE1_GRADE"] = ''
            row[f"SUB{i}_CE2_MRKS"] = ''
            row[f"SUB{i}_CE2_GRADE"] = ''
            row[f"SUB{i}_CE3_MRKS"] = ''
            row[f"SUB{i}_CE3_GRADE"] = ''
            row[f"SUB{i}_CE4_MRKS"] = ''
            row[f"SUB{i}_CE4_GRADE"] = ''
            row[f"SUB{i}_VV_MRKS"] = ''
            row[f"SUB{i}_PAPER1_MRKS"] = ''
            row[f"SUB{i}_PAPER2_MRKS"] = ''
            row[f"SUB{i}_PAPER3_MRKS"] = ''
            row[f"SUB{i}_PAPER4_MRKS"] = ''
            row[f"SUB{i}_PAPER1_PR_MRKS"] = ''
            row[f"SUB{i}_PAPER2_PR_MRKS"] = ''
            row[f"SUB{i}_PAPER3_PR_MRKS"] = ''
            row[f"SUB{i}_PAPER1_CE_MRKS"] = ''
            row[f"SUB{i}_PAPER2_CE_MRKS"] = ''
            row[f"SUB{i}_PAPER3_CE_MRKS"] = ''
            row[f"SUB{i}_PAPER1_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER1_CE_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER1_PR_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER2_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER2_CE_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER2_PR_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER3_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER3_CE_MRKS_SH"] = ''
            row[f"SUB{i}_PAPER3_PR_MRKS_SH"] = ''
            row[f"SUB{i}_MAX_MRKS_SH"] = ''
            row[f"SUB{i}_MAX_CE_MRKS_SH"] = ''
            row[f"SUB{i}_MAX_PR_MRKS_SH"] = ''
            row[f"SUB{i}_MIN_MRKS_SH"] = ''
            row[f"SUB{i}_MIN_CE_MRKS_SH"] = ''
            row[f"SUB{i}_MIN_PR_MRKS_SH"] = ''
            row[f"SUB{i}_LAB1_MRKS"] = ''
            row[f"SUB{i}_LAB2_MRKS"] = ''
            row[f"SUB{i}_LAB3_MRKS"] = ''
            row[f"SUB{i}_LAB4_MRKS"] = ''
            row[f"SUB{i}_LAB1_GRADE"] = ''
            row[f"SUB{i}_LAB2_GRADE"] = ''
            row[f"SUB{i}_LAB3_GRADE"] = ''
            row[f"SUB{i}_LAB4_GRADE"] = ''
            row[f"SUB{i}_REPORT_MRKS"] = ''
            row[f"SUB{i}_REPORT_GRADE"] = ''
            row[f"SUB{i}_PRO_MRKS"] = ''
            row[f"SUB{i}_PRO_CE_MRKS"] = ''
            row[f"SUB{i}_TEE_PR_MRKS"] = ''
            row[f"SUB{i}_TEE_TH_MRKS"] = ''
            row[f"SUB{i}_TEE_PR_GRADE"] = ''
            row[f"SUB{i}_TEE_TH_GRADE"] = ''
            row[f"SUB{i}_TEE_WEIGHT_MRKS"] = ''
            row[f"SUB{i}_TYPE"] = ''
            row[f"SUB{i}_TOT"] = course.get("marks", 0) if pd.notna(course.get("marks")) else 0
            row[f"SUB{i}_CE_TOT"] = ''
            row[f"SUB{i}_PR_TOT"] = ''
            row[f"SUB{i}_REMARKS"] = ''
            row[f"SUB{i}_STATUS"] = course.get("is_failed", "PASS")
            row[f"SUB{i}_GRADE"] = course.get("grade", "")
            row[f"SUB{i}_GRADE_POINTS"] = course.get("grade_point", 0) if pd.notna(course.get("grade_point")) else 0
            row[f"SUB{i}_CREDIT"] = course.get("course_credits", 0) if pd.notna(course.get("course_credits")) else 0
            row[f"SUB{i}_CREDIT_POINTS"] = course.get("credit_points", 0) if pd.notna(course.get("credit_points")) else 0
            row[f"SUB{i}_CREDIT_ELIGIBILITY"] = ''
            row[f"SUB{i}_CREDIT_HOURS"] = ''
            row[f"SUB{i}_PAPER1_STATUS"] = ''
            row[f"SUB{i}_PAPER2_STATUS"] = ''
            row[f"SUB{i}_PAPER3_STATUS"] = ''
            row[f"SUB{i}_PAPER4_STATUS"] = ''
            row[f"SUB{i}_GRACE"] = ''
            row[f"SUB{i}_GROUP"] = ''
            row[f"SUB{i}_GROUP_CODE"] = ''
            row[f"SUB{i}_GROUP_MAX"] = ''
            row[f"SUB{i}_GROUP_MIN"] = ''
            row[f"SUB{i}_GROUP_TOT"] = ''
            row[f"SUB{i}NON_CREDIT_HOURS"] = ''
            
            tot_max += course.get("maximum_marks", 0) if pd.notna(course.get("maximum_marks")) else 0
            tot_min += course.get("minimum_marks", 0) if pd.notna(course.get("minimum_marks")) else 0
            tot_marks += course.get("marks", 0) if pd.notna(course.get("marks")) else 0
            tot_grade_point += course.get("grade_point", 0) if pd.notna(course.get("grade_point")) else 0
            tot_credits += course.get("course_credits", 0) if pd.notna(course.get("course_credits")) else 0
            tot_credit_points += course.get("credit_points", 0) if pd.notna(course.get("credit_points")) else 0
        
        # Get SGPA and CGPA from the last course in group (they should be same for all courses)
        row["SGPA"] = group.iloc[-1].get('sgpa') if 'sgpa' in group.columns else None
        row["CGPA"] = group.iloc[-1].get('cgpa') if 'cgpa' in group.columns else None
        row["TERM_TYPE"] = group.iloc[-1].get('system', '')

        # SESSION = the term's academic-year span (e.g. 2024-2025), same for all courses in group.
        ay_start = group.iloc[-1].get('acad_year_start') if 'acad_year_start' in group.columns else None
        ay_end = group.iloc[-1].get('acad_year_end') if 'acad_year_end' in group.columns else None
        if pd.notna(ay_start) and pd.notna(ay_end):
            row["SESSION"] = f"{int(ay_start)}-{int(ay_end)}"
        else:
            row["SESSION"] = ''

        # NCrF level — derived from programme type + year of study (same for all courses in group).
        # Stored historically per term, not from the student's current/latest level.
        ncrf_ptype = group.iloc[-1].get('programme_type') if 'programme_type' in group.columns else None
        ncrf_yos = group.iloc[-1].get('year_of_study') if 'year_of_study' in group.columns else None
        row["NCRF_LEVEL"] = compute_ncrf_level(ncrf_ptype, ncrf_yos)
        
        row["TOT_MAX"] = tot_max
        row["TOT_MIN"] = tot_min
        row["TOT_MRKS"] = tot_marks
        row["TOT_MRKS_WRDS"] = num2words(int(tot_marks)).title() if tot_marks > 0 else ''
        row["TOT_GRADE_POINTS"] = tot_grade_point
        row["TOT_CREDIT"] = tot_credits
        row["TOT_CREDIT_POINTS"] = tot_credit_points
        
        max_courses = max(max_courses, len(group))
        records.append(row)
    
    final_df = pd.DataFrame(records)
    
    # Create column order
    base_cols = ["student_ukid", "term_name", "sem_year_no"]
    other_cols = ["SGPA", "CGPA", "TERM_TYPE", "NCRF_LEVEL", "SESSION"]
    course_cols = []
    for i in range(1, max_courses + 1):
        course_cols += [
            f"SUB{i}NM", f"SUB{i}", f"SUB{i}MAX", f"SUB{i}MIN", f"SUB{i}_IntMarks", f"SUB{i}_ExtMarks",
            f"SUB{i}_SESSION", f"SUB{i}_TH_MAX", f"SUB{i}_TH_MIN",
            f"SUB{i}_PR_MAX", f"SUB{i}_PR_MIN", f"SUB{i}_CE_MAX", f"SUB{i}_CE_MIN", f"SUB{i}_VV_MAX", f"SUB{i}_VV_MIN",
            f"SUB{i}_VV_GRADE", f"SUB{i}_TH_MRKS", f"SUB{i}_TH_CE_MAX", f"SUB{i}_TH_CE_MRKS", f"SUB{i}_TH_GRADE",
            f"SUB{i}_TH_AGGREGATE", f"SUB{i}_PR_AGGREGATE", f"SUB{i}_PR_MRKS", f"SUB{i}_PR_GRADE", f"SUB{i}_PR_CE_MAX",
            f"SUB{i}_PR_CE_MRKS", f"SUB{i}_PR_HOURS", f"SUB{i}_TH_HOURS", f"SUB{i}_TT_HOURS", f"SUB{i}_CE_WEIGHT_MRKS",
            f"SUB{i}_CE_MRKS", f"SUB{i}_CE_GRADE", f"SUB{i}_CE1_MRKS", f"SUB{i}_CE1_GRADE", f"SUB{i}_CE2_MRKS",
            f"SUB{i}_CE2_GRADE", f"SUB{i}_CE3_MRKS", f"SUB{i}_CE3_GRADE", f"SUB{i}_CE4_MRKS", f"SUB{i}_CE4_GRADE",
            f"SUB{i}_VV_MRKS", f"SUB{i}_PAPER1_MRKS", f"SUB{i}_PAPER2_MRKS", f"SUB{i}_PAPER3_MRKS", f"SUB{i}_PAPER4_MRKS",
            f"SUB{i}_PAPER1_PR_MRKS", f"SUB{i}_PAPER2_PR_MRKS", f"SUB{i}_PAPER3_PR_MRKS", f"SUB{i}_PAPER1_CE_MRKS",
            f"SUB{i}_PAPER2_CE_MRKS", f"SUB{i}_PAPER3_CE_MRKS", f"SUB{i}_PAPER1_MRKS_SH", f"SUB{i}_PAPER1_CE_MRKS_SH",
            f"SUB{i}_PAPER1_PR_MRKS_SH", f"SUB{i}_PAPER2_MRKS_SH", f"SUB{i}_PAPER2_CE_MRKS_SH", f"SUB{i}_PAPER2_PR_MRKS_SH",
            f"SUB{i}_PAPER3_MRKS_SH", f"SUB{i}_PAPER3_CE_MRKS_SH", f"SUB{i}_PAPER3_PR_MRKS_SH", f"SUB{i}_MAX_MRKS_SH",
            f"SUB{i}_MAX_CE_MRKS_SH", f"SUB{i}_MAX_PR_MRKS_SH", f"SUB{i}_MIN_MRKS_SH", f"SUB{i}_MIN_CE_MRKS_SH",
            f"SUB{i}_MIN_PR_MRKS_SH", f"SUB{i}_LAB1_MRKS", f"SUB{i}_LAB2_MRKS", f"SUB{i}_LAB3_MRKS", f"SUB{i}_LAB4_MRKS",
            f"SUB{i}_LAB1_GRADE", f"SUB{i}_LAB2_GRADE", f"SUB{i}_LAB3_GRADE", f"SUB{i}_LAB4_GRADE", f"SUB{i}_REPORT_MRKS",
            f"SUB{i}_REPORT_GRADE", f"SUB{i}_PRO_MRKS", f"SUB{i}_PRO_CE_MRKS", f"SUB{i}_TEE_PR_MRKS", f"SUB{i}_TEE_TH_MRKS",
            f"SUB{i}_TEE_PR_GRADE", f"SUB{i}_TEE_TH_GRADE", f"SUB{i}_TEE_WEIGHT_MRKS", f"SUB{i}_TYPE",
            f"SUB{i}_TOT", f"SUB{i}_CE_TOT", f"SUB{i}_PR_TOT", f"SUB{i}_REMARKS",
            f"SUB{i}_STATUS", f"SUB{i}_GRADE", f"SUB{i}_GRADE_POINTS",
            f"SUB{i}_CREDIT", f"SUB{i}_CREDIT_POINTS",
            f"SUB{i}CREDIT_ELIGIBILITY", f"SUB{i}_CREDIT_HOURS", f"SUB{i}_PAPER1_STATUS", f"SUB{i}_PAPER2_STATUS",
            f"SUB{i}_PAPER3_STATUS", f"SUB{i}_PAPER4_STATUS", f"SUB{i}_GRACE", f"SUB{i}_GROUP",
            f"SUB{i}_GROUP_CODE", f"SUB{i}_GROUP_MAX", f"SUB{i}_GROUP_MIN", f"SUB{i}_GROUP_TOT", f"SUB{i}_NON_CREDIT_HOURS"
        ]
    total_cols = ["TOT_MAX", "TOT_MIN", "TOT_MRKS", "TOT_MRKS_WRDS", "TOT_GRADE_POINTS", "TOT_CREDIT", "TOT_CREDIT_POINTS"]
    
    final_df = final_df.reindex(columns=base_cols + other_cols + course_cols + total_cols)
    
    return final_df

def merge_with_user_details(df_courses, df_user_details):
    """Merge course data with user details"""
    logger.info("Merging course data with user details...")
    
    merged_df = pd.merge(df_user_details, df_courses, on="student_ukid", how="inner")
    return merged_df

def format_final_report(df):
    """Format final report with column ordering and transformations"""
    logger.info("Formatting final report...")

    # Organisation-level columns (ORG_*) are the same institution for every student,
    # so force them to a single value taken from the first row (first non-null, to
    # avoid picking up an empty leading cell) and broadcast it to all rows.
    if not df.empty:
        org_cols = [col for col in df.columns if col.startswith("ORG_")]
        for col in org_cols:
            non_null = df[col].dropna()
            df[col] = non_null.iloc[0] if not non_null.empty else df[col].iloc[0]

    # Rename sem_year_no to SEM
    df.rename(columns={"sem_year_no": "SEM"}, inplace=True)
    
    # Convert SEM to Roman numerals
    roman_map = {
        1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V',
        6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X',
        11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV'
    }
    df['SEM'] = df['SEM'].map(roman_map).fillna(df['SEM'])
    
    # Ensure ABC ID column exports as integer instead of text
    abc_id_col = "ABC_ACCOUNT_ID"
    if abc_id_col in df.columns:
        df[abc_id_col] = pd.to_numeric(df[abc_id_col], errors="coerce").astype("Int64")
    
    # Calculate RESULT based on status columns
    status_cols = [col for col in df.columns if col.endswith("_STATUS")]
    if status_cols:
        df["RESULT"] = df[status_cols].eq("FAIL").any(axis=1).map({True: "FAIL", False: "PASS"})
    else:
        df["RESULT"] = "PASS"
    
    # Define desired column order
    desired_order = [
        "student_ukid", "term_name", "ORG_CODE", "ORG_NAME", "ORG_NAME_L", "ORG_ADDRESS", "ORG_CITY", "ORG_STATE", "ORG_PIN",
        "ACADEMIC_COURSE_ID", "COURSE_NAME", "COURSE_NAME_L", "COURSE_SUBTITLE", "ADMISSION_YEAR",
        "INTR_COURSE_NAME_FIRST", "INTR_COURSE_NAME_SECOND", "DEPARTMENT", "STREAM", "STREAM_L",
        "STREAM_SECOND", "STREAM_SECOND_L", "SPECIALIZATION_MAJOR", "SPECIALIZATION_MINOR",
        "SESSION", "REGN_NO", "APPLICATION_NUMBER", "RROLL", "ABC_ACCOUNT_ID", "CNAME", "AADHAAR_NAME", "GENDER", "DOB",
        "BLOOD_GROUP", "CASTE", "RELIGION", "NATIONALITY", "PH", "MOBILE", "EMAIL", "FNAME",
        "MNAME", "GNAME", "STUDENT_ADDRESS", "PHOTO", "MRKS_REC_STATUS", "RESULT", "RESULT_TH",
        "RESULT_PR", "YEAR", "MONTH", "DIVISION", "GRADE", "PERCENT", "DOR", "DOI", "DOV", "DOE", "DOP",
        "DOQ", "DOS", "THESIS", "REMARKS", "CERT_NO", "MEDIUM", "SEM", "CENTRE_NAME", "EXAM_TYPE", "TERM_TYPE",
        "TOT", "TOT_MAX", "TOT_MIN", "TOT_MRKS", "TOT_MRKS_WRDS", "TOT_MRKS_MIN",
        "TOT_TH_MAX", "TOT_TH_MIN", "TOT_TH_MRKS", "TOT_PR_MAX", "TOT_PR_MIN", "TOT_PR_MRKS",
        "TOT_CE_MAX", "TOT_CE_MIN", "TOT_CE_MRKS", "TOT_VV_MAX", "TOT_VV_MIN", "TOT_VV_MRKS",
        "TOT_PR_CE_MAX", "TOT_PR_CE_MRKS", "TOT_TH_CE_MAX", "TOT_TH_CE_MRKS", "PREV_TOT_MRKS",
        "PREV_TOT_MRKS_MAX", "PREV_TOT_MRKS_MIN", "GRAND_TOT_MAX", "GRAND_TOT_MIN",
        "GRAND_TOT_MRKS", "TOT_GRADE", "TOT_GRADE_POINTS", "TOT_CREDIT", "TOT_CREDIT_POINTS",
        "GRAND_TOT_GRADE_POINTS", "GRAND_TOT_CREDIT", "GRAND_TOT_CREDIT_POINTS", "CGPA",
        "TOT_CGPA_MINOR", "TOT_CREDIT_MINOR", "CGPA_SCALE", "SGPA", "GPA",
        "INTR_CGPA_FIRST", "INTR_CGPA_SECOND"
    ]
    
    remaining_cols = [col for col in df.columns if col not in desired_order]
    final_column_order = desired_order + remaining_cols
    
    # Reorder columns (only include columns that exist)
    final_column_order = [col for col in final_column_order if col in df.columns]
    final_column_order.extend([col for col in remaining_cols if col not in final_column_order])
    
    df_reordered = df.reindex(columns=final_column_order)
    
    return df_reordered

# ============================================================================
# TEMPLATE COLUMN FILTERING
# ============================================================================

SUBJECT_COL_RE = re.compile(r'^SUB(\d+)(.*)$')


def load_template_columns(template_path):
    """Read the header row of the uploaded template file and return its columns in order."""
    p = Path(template_path)
    if not p.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")
    if p.suffix.lower() in ('.xlsx', '.xls'):
        tdf = pd.read_excel(p, nrows=0)
    else:
        tdf = pd.read_csv(p, nrows=0)
    return list(tdf.columns)


def apply_template_columns(df, template_cols):
    """Restrict df to the template's columns, expanding the single subject block
    (SUB1...) found in the template to cover every subject present in df.

    The template lists subject columns once (for subject 1, e.g. after DEPARTMENT).
    That same block of columns is repeated for SUB2, SUB3, ... up to the maximum
    number of subjects produced for any student. All other (student-level) columns
    are kept exactly as they appear in the template; any column not produced by the
    report is added empty so the output matches the template exactly.
    """
    logger.info("Applying template columns...")

    # Determine the max subject index present in the generated data
    max_subjects = 0
    for col in df.columns:
        m = SUBJECT_COL_RE.match(col)
        if m:
            max_subjects = max(max_subjects, int(m.group(1)))

    # Subject-column suffixes from the template, in template order (e.g. 'NM', '', '_TOT').
    # Only take the FIRST subject block — the template may list more than one sample
    # subject (SUB1..., SUB2...); we replicate a single block, not all of them.
    subject_suffixes = []
    first_subject_num = None
    for col in template_cols:
        m = SUBJECT_COL_RE.match(col)
        if m:
            if first_subject_num is None:
                first_subject_num = m.group(1)
            if m.group(1) == first_subject_num:
                subject_suffixes.append(m.group(2))

    # Build the final ordered column list: keep template order, but at the position
    # of the first subject column, expand the whole subject block for subjects 1..N.
    final_cols = []
    expanded = False
    for col in template_cols:
        if SUBJECT_COL_RE.match(col):
            if not expanded:
                for i in range(1, max_subjects + 1):
                    for suffix in subject_suffixes:
                        final_cols.append(f"SUB{i}{suffix}")
                expanded = True
            # other subject columns from the template are part of the same block; skip
            continue
        final_cols.append(col)

    # Add any template columns the report didn't produce as empty columns
    for col in final_cols:
        if col not in df.columns:
            df[col] = ''

    return df[final_cols]


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    print("="*60)
    print("NAD REPORT GENERATOR")
    print("="*60)
    
    # Get inputs
    tenant_name = input("\nEnter tenant name: ").strip()
    if not tenant_name:
        print("Error: Tenant name cannot be empty!")
        return
    
    term_id_input = input("Enter term ID(s) (comma-separated for multiple): ").strip()
    if not term_id_input:
        print("Error: Term ID cannot be empty!")
        return

    try:
        # Accept one or many comma-separated term IDs; de-duplicate while preserving order
        term_ids = []
        for part in term_id_input.split(','):
            part = part.strip()
            if not part:
                continue
            tid = int(part)
            if tid not in term_ids:
                term_ids.append(tid)
        if not term_ids:
            raise ValueError("no valid term IDs")
    except ValueError:
        print("Error: Term ID(s) must be valid integers (e.g. 12 or 12,15,18)!")
        return
    print(f"Term ID(s): {', '.join(str(t) for t in term_ids)}")
    
    # Get exam type input (0 for exam, 1 for re-exam)
    exam_type_input = input("Enter exam type (0 for Exam, 1 for Re-exam): ").strip()
    if exam_type_input not in ['0', '1']:
        print("Error: Exam type must be 0 (Exam) or 1 (Re-exam)!")
        return
    
    is_re_exam = (exam_type_input == '1')
    if is_re_exam:
        print(f"\nUsing RE-EXAM mode")
    else:
        print(f"\nUsing NORMAL EXAM mode")

    # Get template file (defines which columns appear in the output)
    template_path = input("\nEnter path to template file (defines output columns): ").strip().strip('"')
    if not template_path:
        print("Error: Template file path cannot be empty!")
        return
    try:
        template_cols = load_template_columns(template_path)
    except Exception as e:
        print(f"Error: Could not read template file - {e}")
        return
    print(f"Loaded {len(template_cols)} columns from template")

    # Gradesheet date fields — only prompt for the ones present in the template; each
    # entered value is hardcoded for every student in this run.
    template_set = set(template_cols)

    def _ask_if_in_template(col, label):
        if col in template_set:
            return input(f"Enter {label} ({col}): ").strip()
        return ''

    doi_input = _ask_if_in_template('DOI', 'Date of Issue')

    # Month & Year of Exam captured in a single prompt, then split into the two columns.
    month_input = year_input = ''
    if 'MONTH' in template_set or 'YEAR' in template_set:
        my_raw = input("Enter Month and Year of Exam (e.g. June 2024): ").strip()
        year_match = re.search(r'\d{4}', my_raw)
        if year_match:
            year_input = year_match.group(0)
            month_input = my_raw.replace(year_input, '').strip(' /,-').strip()
        else:
            month_input = my_raw

    # Connect to database
    print("\nConnecting to database...")
    conn = connect_to_tenant_database(tenant_name)
    
    try:
        # Fetch data — all term IDs are fetched together (one query each) to keep DB load low
        print("\nFetching data from database...")
        df_exam = fetch_exam_data(conn, term_ids, is_re_exam)

        if df_exam.empty:
            print("Error: No exam data found!")
            return

        # Extract student UKIDs from exam data
        student_ukids = df_exam['student_ukid'].unique().tolist()
        logger.info(f"Found {len(student_ukids)} unique students")

        df_cgpa = fetch_cgpa_data(conn, term_ids)
        df_sgpa = fetch_sgpa_data(conn, term_ids)
        df_int_ext = fetch_subjectwise_int_ext(conn, term_ids)
        df_user_details = fetch_user_details(conn, tenant_name, student_ukids)

        # Process data
        print("\nProcessing data...")
        df_exam = merge_exam_data_with_schema(df_exam, df_cgpa, df_sgpa)
        df_exam = process_course_data(df_exam)

        # Create course records (with subjectwise Internal/External marks)
        df_courses = create_course_records(df_exam, df_int_ext)

        # Merge with user details
        df_merged = merge_with_user_details(df_courses, df_user_details)

        # Exam type: 'Regular' for normal exam, 'Backlog' for re-exam
        df_merged['EXAM_TYPE'] = 'Backlog' if is_re_exam else 'Regular'

        # Date of Issue / Month / Year — hardcoded from user input for every student in this run
        df_merged['DOI'] = doi_input
        df_merged['MONTH'] = month_input
        df_merged['YEAR'] = year_input

        # Format final report
        df_final = format_final_report(df_merged)

        # Save output — one file per term
        output_dir = Path(r"C:\Users\suraj\OneDrive\Desktop\NAD Report Outputs")
        output_dir.mkdir(parents=True, exist_ok=True)

        tenant_output_dir = output_dir / tenant_name
        tenant_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"NAD REPORT GENERATION COMPLETE!")
        print(f"{'='*60}")

        # Split by term BEFORE template filtering (term_name may not be a template column),
        # then restrict each term's output to the template's columns.
        if 'term_name' in df_final.columns:
            for term_name, df_term in df_final.groupby('term_name'):
                df_term_out = apply_template_columns(df_term.copy(), template_cols)
                term_name_clean = str(term_name).replace('/', '_').replace('\\', '_').replace(':', '_')
                output_file = tenant_output_dir / f"NAD_{term_name_clean}.xlsx"
                df_term_out.to_excel(output_file, index=False)
                print(f"Report saved: {output_file} ({len(df_term_out)} rows)")
        else:
            df_out = apply_template_columns(df_final, template_cols)
            term_label = '_'.join(str(t) for t in term_ids)
            output_file = tenant_output_dir / f"NAD_Terms_{term_label}.xlsx"
            df_out.to_excel(output_file, index=False)
            print(f"Report saved: {output_file} ({len(df_out)} rows)")

        print(f"Location: {tenant_output_dir}")

    finally:
        conn.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()
