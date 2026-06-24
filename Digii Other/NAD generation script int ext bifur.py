import pandas as pd
import numpy as np
from num2words import num2words
import mysql.connector
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')


def connect_to_db():
    return mysql.connector.connect(
        host="collpolldb19-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        user="suraj_shetty",
        password="LW3J0MU3mZ",
        database="collpoll_mujbl"
    )


QUERY_EXAM_DATA = """
SELECT
    t.name as term_name,
    eesc.student_ukid,
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
    tc.id as term_course_id,
    COALESCE(max_internal_marks, 0) + COALESCE(max_external_marks, 0) AS maximum_marks,
    COALESCE(min_external_marks, 0) + COALESCE(min_internal_marks, 0) AS minimum_marks,
    eesc.marks,
    CASE WHEN (eesc.is_failed) >= 1 THEN 'FAIL' ELSE 'PASS' END is_failed,
    eesc.grade,
    eesc.grade_point,
    (eesc.grade_point * tc.course_credits) AS credit_points,
    cgpa.cgpa,
    sgpa.sgpa
FROM ems_student_programme_enrollment esp
INNER JOIN ems_student_course_enrollment esc ON esc.student_programme_enrollment_id = esp.id
INNER JOIN ems_examination ee ON ee.id = esp.exam_id
INNER JOIN term_course tc ON tc.id = esc.term_course_id
INNER JOIN ems_examination_student_course_grade eesc ON eesc.term_course_id = tc.id AND eesc.student_ukid = esp.ukid
INNER JOIN term t ON t.id = ee.term_id
INNER JOIN student_profile sp ON sp.ukid = eesc.student_ukid
LEFT JOIN programme p ON p.programme_id = sp.programme_id
INNER JOIN ems_examination_course_schema ecs ON ecs.examination_id = eesc.examination_id AND ecs.course_id = eesc.course_id
LEFT JOIN (
    SELECT exam_id, student_ukid, COALESCE(re_exam_cgpa, cgpa) AS cgpa,
        ROW_NUMBER() OVER (PARTITION BY exam_id, student_ukid ORDER BY id DESC) AS rn
    FROM ems_examination_student_cgpa
) cgpa ON cgpa.exam_id = ee.id AND cgpa.student_ukid = eesc.student_ukid AND cgpa.rn = 1
LEFT JOIN (
    SELECT exam_id, student_ukid, COALESCE(re_exam_sgpa, sgpa) AS sgpa,
        ROW_NUMBER() OVER (PARTITION BY exam_id, student_ukid ORDER BY id DESC) AS rn
    FROM ems_examination_student_sgpa
) sgpa ON sgpa.exam_id = ee.id AND sgpa.student_ukid = eesc.student_ukid AND sgpa.rn = 1
INNER JOIN (
    SELECT
        examination_schema_id,
        MAX(CASE WHEN label = 'Internal' THEN max_weightage END) AS max_internal_marks,
        MAX(CASE WHEN label = 'External' THEN max_weightage END) AS max_external_marks,
        MIN(CASE WHEN label = 'Internal' THEN min_weightage END) AS min_internal_marks,
        MIN(CASE WHEN label = 'External' THEN min_weightage END) AS min_external_marks
    FROM (
        SELECT
            examination_schema_id,
            eect.name AS label,
            SUM((eescon.weightage * maximum_marks) / 100) AS max_weightage,
            SUM((eescon.weightage * minimum_marks) / 100) AS min_weightage
        FROM ems_examination_schema_composition eescon
        LEFT JOIN ems_examination_schema_component eescot ON eescon.schema_component_id = eescot.id
        LEFT JOIN ems_examination_component_type eect ON eect.id = eescot.component_type_id
        GROUP BY examination_schema_id, eect.name
    ) AS component_weights
    GROUP BY examination_schema_id
) ees ON ees.examination_schema_id = ecs.examination_schema_id
WHERE t.id = {TERM_ID}
    AND esc.enrollment_status != 'NOT_ENROLLED'
GROUP BY eesc.student_ukid, tc.course_code, t.name
"""

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
WHERE tc.term_id = {TERM_ID}
    AND eect.name IN ('Internal', 'External')
GROUP BY eesm.student_ukid, eesm.term_course_id, eect.name
"""

QUERY_USER_DETAILS = """
SELECT
    ua.ukid AS student_ukid,
    c.college_name AS ORG_NAME,
    c.address AS ORG_ADDRESS,
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
FROM user_attributes ua
INNER JOIN authenticator a ON a.ukid = ua.ukid
INNER JOIN student_profile sp ON sp.ukid = ua.ukid
INNER JOIN programme p ON p.programme_id = sp.programme_id
INNER JOIN department d ON d.department_id = p.department_id
INNER JOIN college c ON c.college_id = d.college_id
WHERE ua.ukid IN ({UKIDS})
"""

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
FROM user_details_master_field_value t1
LEFT JOIN user_details_master_field t2 ON t1.field_id = t2.id
WHERE t2.identifier IN (
    'FATHER_NAME', 'FATHER_FIRST_NAME', 'FATHER_MIDDLE_NAME', 'FATHER_LAST_NAME',
    'GUARDIAN_NAME', 'GUARDIAN_FIRST_NAME', 'GUARDIAN_MIDDLE_NAME', 'GUARDIAN_LAST_NAME',
    'FATHERS_TITLE', 'MOTHERS_TITLE',
    'MOTHER_NAME', 'MOTHER_FIRST_NAME', 'MOTHER_MIDDLE_NAME', 'MOTHER_LAST_NAME',
    'UNIVERSITY_ROLL_NUMBER', 'CERTIFICATE_NAME', 'DATE_OF_BIRTH', 'ACADEMIC_BANK_OF_CREDIT_ID',
    'CASTE', 'RELIGION', 'NATIONALITY', 'PERMANENT_ADDRESS'
)
AND t1.ukid IN ({UKIDS})
GROUP BY t1.ukid
"""

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


def run_query(conn, query):
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    return pd.DataFrame(rows, columns=columns)


def fetch_exam_data(conn, term_id):
    return run_query(conn, QUERY_EXAM_DATA.format(TERM_ID=term_id))


def fetch_subjectwise_int_ext(conn, term_id):
    df = run_query(conn, QUERY_SUBJECTWISE_INT_EXT.format(TERM_ID=term_id))
    if df.empty:
        return pd.DataFrame(columns=['student_ukid', 'term_course_id', 'Internal', 'External'])
    pivot = df.pivot_table(
        index=['student_ukid', 'term_course_id'],
        columns='label', values='marks', aggfunc='sum'
    ).reset_index()
    for col in ('Internal', 'External'):
        if col not in pivot.columns:
            pivot[col] = np.nan
    return pivot[['student_ukid', 'term_course_id', 'Internal', 'External']]


def fetch_user_details(conn, student_ukids):
    if not student_ukids:
        return pd.DataFrame()
    ukids_str = ','.join(f"'{u}'" for u in student_ukids)

    df_attrs = run_query(conn, QUERY_USER_DETAILS.format(UKIDS=ukids_str))
    df_master = run_query(conn, QUERY_USER_DETAILS_MASTER.format(UKIDS=ukids_str))
    df_spec = run_query(conn, QUERY_SPECIALISATIONS.format(UKIDS=ukids_str))

    df_user = df_attrs.copy()

    if not df_master.empty:
        df_master['RROLL'] = df_master['university_roll_number']
        df_master['ABC_ACCOUNT_ID'] = df_master['abc_id']
        df_master['AADHAAR_NAME'] = df_master['aadhar_name']
        df_master['DOB'] = pd.to_datetime(df_master['dob'], errors='coerce').dt.strftime('%d/%m/%Y')
        df_master['CASTE'] = df_master['C']
        df_master['RELIGION'] = df_master['Re']
        df_master['NATIONALITY'] = df_master['Nat']
        df_master['FNAME'] = df_master.apply(
            lambda r: r['father_name'] if pd.notna(r['father_name'])
            else ' '.join(filter(None, [r.get('father_first_name'), r.get('father_middle_name'), r.get('father_last_name')])),
            axis=1
        )
        df_master['MNAME'] = df_master.apply(
            lambda r: r['mother_name'] if pd.notna(r['mother_name'])
            else ' '.join(filter(None, [r.get('mother_first_name'), r.get('mother_middle_name'), r.get('mother_last_name')])),
            axis=1
        )
        df_master['GNAME'] = df_master.apply(
            lambda r: r['guardian_name'] if pd.notna(r['guardian_name'])
            else ' '.join(filter(None, [r.get('guardian_first_name'), r.get('guardian_middle_name'), r.get('guardian_last_name')])),
            axis=1
        )
        df_master['STUDENT_ADDRESS'] = df_master['pt']
        df_user = df_user.merge(
            df_master[['ukid', 'RROLL', 'ABC_ACCOUNT_ID', 'AADHAAR_NAME', 'DOB',
                       'CASTE', 'RELIGION', 'NATIONALITY', 'FNAME', 'MNAME', 'GNAME', 'STUDENT_ADDRESS']],
            left_on='student_ukid', right_on='ukid', how='left'
        ).drop(columns=['ukid'])

    if not df_spec.empty:
        df_spec['SPECIALIZATION_MAJOR'] = df_spec['major']
        df_spec['SPECIALIZATION_MINOR'] = df_spec['minor']
        df_user = df_user.merge(
            df_spec[['ukid', 'SPECIALIZATION_MAJOR', 'SPECIALIZATION_MINOR']],
            left_on='student_ukid', right_on='ukid', how='left'
        ).drop(columns=['ukid'])
    else:
        df_user['SPECIALIZATION_MAJOR'] = None
        df_user['SPECIALIZATION_MINOR'] = None

    df_user['SESSION'] = df_user.apply(
        lambda r: f"{r['ADMISSION_YEAR']}-{r['ADMISSION_YEAR'] + 1}" if pd.notna(r['ADMISSION_YEAR']) else None,
        axis=1
    )
    return df_user


def create_course_records(df_exam, df_int_ext):
    df = df_exam.merge(df_int_ext, on=['student_ukid', 'term_course_id'], how='left')
    df.sort_values(by=['student_ukid', 'term_name', 'sem_year_no', 'course_code'], inplace=True)

    records = []
    max_courses = 0
    grouped = df.groupby(['student_ukid', 'term_name', 'sem_year_no'])

    for (ukid, term, sem), group in grouped:
        row = {'student_ukid': ukid, 'term_name': term, 'sem_year_no': sem}

        tot_max = tot_min = tot_marks = tot_grade_point = tot_credits = tot_credit_points = 0

        for i, (_, course) in enumerate(group.iterrows(), 1):
            internal_val = course.get('Internal')
            external_val = course.get('External')
            total_marks_val = course.get('marks', 0) if pd.notna(course.get('marks')) else 0

            if pd.isna(internal_val) and pd.isna(external_val):
                internal_val = total_marks_val
                external_val = 0
            else:
                internal_val = internal_val if pd.notna(internal_val) else np.nan
                external_val = external_val if pd.notna(external_val) else np.nan

            row[f"SUB{i}NM"] = course["course_name"]
            row[f"SUB{i}"] = course["course_code"]
            row[f"SUB{i}MAX"] = course["maximum_marks"]
            row[f"SUB{i}MIN"] = course["minimum_marks"]
            row[f"SUB{i}_IntMarks"] = internal_val
            row[f"SUB{i}_ExtMarks"] = external_val
            row[f"SUB{i}_TOT"] = total_marks_val
            row[f"SUB{i}_STATUS"] = course.get("is_failed", "PASS")
            row[f"SUB{i}_GRADE"] = course.get("grade", "")
            row[f"SUB{i}_GRADE_POINTS"] = course.get("grade_point", 0) if pd.notna(course.get("grade_point")) else 0
            row[f"SUB{i}_CREDIT"] = course.get("course_credits", 0) if pd.notna(course.get("course_credits")) else 0
            row[f"SUB{i}_CREDIT_POINTS"] = course.get("credit_points", 0) if pd.notna(course.get("credit_points")) else 0

            tot_max += course.get("maximum_marks", 0) if pd.notna(course.get("maximum_marks")) else 0
            tot_min += course.get("minimum_marks", 0) if pd.notna(course.get("minimum_marks")) else 0
            tot_marks += total_marks_val
            tot_grade_point += course.get("grade_point", 0) if pd.notna(course.get("grade_point")) else 0
            tot_credits += course.get("course_credits", 0) if pd.notna(course.get("course_credits")) else 0
            tot_credit_points += course.get("credit_points", 0) if pd.notna(course.get("credit_points")) else 0

        row["SGPA"] = group.iloc[-1].get('sgpa')
        row["CGPA"] = group.iloc[-1].get('cgpa')
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

    base_cols = ["student_ukid", "term_name", "sem_year_no"]
    other_cols = ["SGPA", "CGPA", "TERM_TYPE"]
    course_cols = []
    for i in range(1, max_courses + 1):
        course_cols += [
            f"SUB{i}NM", f"SUB{i}", f"SUB{i}MAX", f"SUB{i}MIN",
            f"SUB{i}_IntMarks", f"SUB{i}_ExtMarks", f"SUB{i}_TOT",
            f"SUB{i}_STATUS", f"SUB{i}_GRADE", f"SUB{i}_GRADE_POINTS",
            f"SUB{i}_CREDIT", f"SUB{i}_CREDIT_POINTS",
        ]
    total_cols = ["TOT_MAX", "TOT_MIN", "TOT_MRKS", "TOT_MRKS_WRDS", "TOT_GRADE_POINTS", "TOT_CREDIT", "TOT_CREDIT_POINTS"]

    return final_df.reindex(columns=base_cols + other_cols + course_cols + total_cols)


def format_final_report(df):
    df = df.rename(columns={"sem_year_no": "SEM"})
    roman_map = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII',
                 8: 'VIII', 9: 'IX', 10: 'X', 11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV'}
    df['SEM'] = df['SEM'].map(roman_map).fillna(df['SEM'])

    if "ABC_ACCOUNT_ID" in df.columns:
        df["ABC_ACCOUNT_ID"] = pd.to_numeric(df["ABC_ACCOUNT_ID"], errors="coerce").astype("Int64")

    status_cols = [c for c in df.columns if c.endswith("_STATUS")]
    df["RESULT"] = df[status_cols].eq("FAIL").any(axis=1).map({True: "FAIL", False: "PASS"}) if status_cols else "PASS"

    desired_order = [
        "student_ukid", "term_name", "ORG_CODE", "ORG_NAME", "ORG_NAME_L", "ORG_ADDRESS", "ORG_CITY", "ORG_STATE", "ORG_PIN",
        "ACADEMIC_COURSE_ID", "COURSE_NAME", "COURSE_NAME_L", "COURSE_SUBTITLE", "ADMISSION_YEAR",
        "INTR_COURSE_NAME_FIRST", "INTR_COURSE_NAME_SECOND", "DEPARTMENT", "STREAM", "STREAM_L",
        "STREAM_SECOND", "STREAM_SECOND_L", "SPECIALIZATION_MAJOR", "SPECIALIZATION_MINOR",
        "SESSION", "REGN_NO", "APPLICATION_NUMBER", "RROLL", "ABC_ACCOUNT_ID", "CNAME", "AADHAAR_NAME", "GENDER", "DOB",
        "MOBILE", "EMAIL", "FNAME", "MNAME", "GNAME", "STUDENT_ADDRESS", "PHOTO", "MRKS_REC_STATUS", "RESULT",
        "SEM", "TERM_TYPE", "TOT_MAX", "TOT_MIN", "TOT_MRKS", "TOT_MRKS_WRDS",
        "TOT_GRADE_POINTS", "TOT_CREDIT", "TOT_CREDIT_POINTS", "CGPA", "SGPA",
    ]
    remaining = [c for c in df.columns if c not in desired_order]
    final_order = [c for c in desired_order if c in df.columns] + remaining
    return df.reindex(columns=final_order)


def main():
    print("=" * 60)
    print("NAD REPORT GENERATOR (with subjectwise Internal/External marks)")
    print("=" * 60)

    term_id_input = input("\nEnter term ID: ").strip()
    try:
        term_id = int(term_id_input)
    except ValueError:
        print("Error: Term ID must be a valid integer!")
        return

    print("\nConnecting to database...")
    conn = connect_to_db()

    try:
        print(f"Fetching exam data for term_id={term_id}...")
        df_exam = fetch_exam_data(conn, term_id)
        if df_exam.empty:
            print("Error: No exam data found for this term ID!")
            return

        print("Fetching subjectwise Internal/External marks...")
        df_int_ext = fetch_subjectwise_int_ext(conn, term_id)
        print(f"  Found Internal/External rows for {len(df_int_ext)} (student, course) pairs")

        student_ukids = df_exam['student_ukid'].unique().tolist()
        print(f"Fetching user details for {len(student_ukids)} students...")
        df_user = fetch_user_details(conn, student_ukids)

        print("\nBuilding subject records...")
        df_courses = create_course_records(df_exam, df_int_ext)

        print("Merging with user details...")
        df_merged = pd.merge(df_user, df_courses, on="student_ukid", how="inner")

        print("Formatting final report...")
        df_final = format_final_report(df_merged)

        term_name = df_exam['term_name'].iloc[0] if not df_exam.empty else f"Term_{term_id}"
        output_dir = Path(r"C:\Users\suraj\OneDrive\Desktop\NAD Report Outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        term_name_clean = str(term_name).replace('/', '_').replace('\\', '_').replace(':', '_')
        output_file = output_dir / f"NAD_{term_name_clean}.csv"

        df_final.to_csv(output_file, index=False)
        print(f"\n{'=' * 60}")
        print("NAD REPORT GENERATION COMPLETE!")
        print(f"{'=' * 60}")
        print(f"Report saved: {output_file}")

    finally:
        conn.close()
        print("\nDatabase connection closed")


if __name__ == "__main__":
    main()