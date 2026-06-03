import pandas as pd
import numpy as np
from num2words import num2words
import os
import sys
import logging
import warnings
from pathlib import Path
from datetime import datetime
import pymysql
from dotenv import load_dotenv

# Add TR Report Progress Archive to path to import helper
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'TR Report Workspace', 'TR Report Progress Archive'))
from helper import connect_to_tenant_database

warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment files from TR Report Progress Archive
archive_path = os.path.join(os.path.dirname(__file__), '..', 'TR Report Workspace', 'TR Report Progress Archive')
load_dotenv(os.path.join(archive_path, 'config.env'))
load_dotenv(os.path.join(archive_path, 'database_index.env'))

# ============================================================================
# EMBEDDED SQL QUERIES - EXAM DATA (SPLIT INTO 2 QUERIES)
# ============================================================================

# Query 1: Exam Details (with examination_schema_id for joining)
QUERY_1_EXAM_DATA = """
SELECT
    t.name as term_name,
    espe.ukid as student_ukid,
    tc.course_code,
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
    p.system,
    tc.course_name,
    tc.course_credits,
    eesc.marks,
    eesc.re_exam_marks as re_exam_ku_marks,
    CASE WHEN (eesc.is_failed) >= 1 THEN 'FAIL' ELSE 'PASS' END is_failed,
    eesc.grade,
    eesc.re_exam_grade as re_exam_ku_grade,
    eesc.grade_point,
    eesc.re_exam_grade_point as re_exam_ku_grade_point,
    (eesc.grade_point * tc.course_credits) AS credit_points,
    (eesc.re_exam_grade_point * tc.course_credits) AS re_exam_ku_credit_points,
    ecs.examination_schema_id 
FROM
    ems_student_programme_enrollment espe
INNER JOIN ems_student_course_enrollment esce 
    ON espe.id = esce.student_programme_enrollment_id
INNER JOIN ems_examination ee
    ON ee.id = espe.exam_id 
INNER JOIN term_course tc
    ON tc.id = esce.term_course_id
INNER JOIN student_profile sp
    ON sp.ukid = espe.ukid
INNER JOIN programme p 
    ON p.programme_id = sp.programme_id 
INNER JOIN term t 
    ON t.id = ee.term_id
INNER JOIN ems_examination_student_course_grade eesc
    ON eesc.term_course_id = tc.id AND eesc.student_ukid = espe.ukid
INNER JOIN ems_examination_course_schema ecs 
    ON ecs.examination_id = ee.id AND ecs.course_id = tc.course_id
WHERE 
    t.id = {TERM_ID}
    AND esce.enrollment_status != 'NOT_ENROLLED'
GROUP BY eesc.student_ukid, tc.course_name, t.name
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
    WHERE t.id = {TERM_ID}
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
    WHERE t.id = {TERM_ID}
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
    null AS ACADEMIC_COURSE_ID,
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
QUERY_SPECIALISATIONS = """
SELECT 
    t2.ukid,
    MAX(CASE WHEN t1.specialisation_type = 'MAJOR' THEN t3.name END) AS major,
    MAX(CASE WHEN t1.specialisation_type = 'MINOR' THEN t3.name END) AS minor
FROM programme_specialisation_mapping t1
LEFT JOIN programme_specialisation_student t2 ON t2.programme_specialisation_mapping_id = t1.id
LEFT JOIN specialisation t3 ON t1.specialisation_id = t3.id 
WHERE t2.ukid IN ({UKIDS})
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

def fetch_exam_data(conn, term_id, is_re_exam=False):
    """Fetch exam data using split queries and process in Python"""
    logger.info(f"Fetching {'re-exam' if is_re_exam else 'normal'} exam data for term_id: {term_id}")
    
    # Query 1: Fetch exam details
    query1 = QUERY_1_EXAM_DATA.replace('{TERM_ID}', str(term_id))
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

def fetch_cgpa_data(conn, term_id):
    """Fetch CGPA data"""
    logger.info("Fetching CGPA data...")
    query = QUERY_2_CGPA.replace('{TERM_ID}', str(term_id))
    
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

def fetch_sgpa_data(conn, term_id):
    """Fetch SGPA data"""
    logger.info("Fetching SGPA data...")
    query = QUERY_3_SGPA.replace('{TERM_ID}', str(term_id))
    
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
        df_spec['SPECIALIZATION_MAJOR'] = df_spec['major']
        df_spec['SPECIALIZATION_MINOR'] = df_spec['minor']
        df_user = df_user.merge(
            df_spec[['ukid', 'SPECIALIZATION_MAJOR', 'SPECIALIZATION_MINOR']],
            on='ukid',
            how='left'
        )
    else:
        df_user['SPECIALIZATION_MAJOR'] = None
        df_user['SPECIALIZATION_MINOR'] = None
    
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
    
    # Add SESSION column
    df_user['SESSION'] = df_user.apply(
        lambda row: f"{row['ADMISSION_YEAR']}-{row['ADMISSION_YEAR'] + 1}" 
        if pd.notna(row['ADMISSION_YEAR']) else None,
        axis=1
    )
    
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

def create_course_records(df_exam):
    """Create course records in NAD format"""
    logger.info("Creating course records in NAD format...")
    
    df = df_exam.copy()
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
            row[f"SUB{i}NM"] = course["course_name"]
            row[f"SUB{i}"] = course["course_code"]
            row[f"SUB{i}MAX"] = course.get("maximum_marks", 0)
            row[f"SUB{i}MIN"] = course.get("minimum_marks", 0)
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
    other_cols = ["SGPA", "CGPA", "TERM_TYPE"]
    course_cols = []
    for i in range(1, max_courses + 1):
        course_cols += [
            f"SUB{i}NM", f"SUB{i}", f"SUB{i}MAX", f"SUB{i}MIN", f"SUB{i}_SESSION", f"SUB{i}_TH_MAX", f"SUB{i}_TH_MIN",
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
    
    term_id_input = input("Enter term ID: ").strip()
    if not term_id_input:
        print("Error: Term ID cannot be empty!")
        return
    
    try:
        term_id = int(term_id_input)
    except ValueError:
        print("Error: Term ID must be a valid integer!")
        return
    
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
    
    # Connect to database
    print("\nConnecting to database...")
    conn = connect_to_tenant_database(tenant_name)
    
    try:
        # Fetch data
        print("\nFetching data from database...")
        df_exam = fetch_exam_data(conn, term_id, is_re_exam)
        
        if df_exam.empty:
            print("Error: No exam data found!")
            return
        
        # Extract student UKIDs from exam data
        student_ukids = df_exam['student_ukid'].unique().tolist()
        logger.info(f"Found {len(student_ukids)} unique students")
        
        df_cgpa = fetch_cgpa_data(conn, term_id)
        df_sgpa = fetch_sgpa_data(conn, term_id)
        df_user_details = fetch_user_details(conn, tenant_name, student_ukids)
        
        # Process data
        print("\nProcessing data...")
        df_exam = merge_exam_data_with_schema(df_exam, df_cgpa, df_sgpa)
        df_exam = process_course_data(df_exam)
        
        # Create course records
        df_courses = create_course_records(df_exam)
        
        # Merge with user details
        df_merged = merge_with_user_details(df_courses, df_user_details)
        
        # Format final report
        df_final = format_final_report(df_merged)
        
        # Get term name for output filename
        term_name = df_exam['term_name'].iloc[0] if 'term_name' in df_exam.columns and not df_exam.empty else f"Term_{term_id}"
        
        # Save output
        output_dir = Path(r"C:\Users\shami\Documents\NAD Report Outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        tenant_output_dir = output_dir / tenant_name
        tenant_output_dir.mkdir(parents=True, exist_ok=True)
        
        term_name_clean = term_name.replace('/', '_').replace('\\', '_').replace(':', '_')
        output_file = tenant_output_dir / f"NAD_{term_name_clean}.csv"
        
        df_final.to_csv(output_file, index=False)
        print(f"\n{'='*60}")
        print(f"NAD REPORT GENERATION COMPLETE!")
        print(f"{'='*60}")
        print(f"Report saved: {output_file}")
        print(f"Location: {tenant_output_dir}")
        
    finally:
        conn.close()
        print("\nDatabase connection closed")

if __name__ == "__main__":
    main()
