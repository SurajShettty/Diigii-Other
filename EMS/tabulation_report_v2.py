import pandas as pd
import numpy as np
import mysql.connector
import xlsxwriter
import gspread as gs
from datetime import date
import datetime
from openpyxl import load_workbook
from openpyxl.styles import Font
import datetime
from pathlib import Path
import requests
import json
import warnings
from pathlib import Path
import os
import shutil


def number_to_alphabet(n):
    if n <= 0:
        return "Invalid input"

    result = ""
    while n > 0:
        remainder = (n - 1) % 26  # Calculate remainder to determine letter
        result = chr(remainder + ord('a')) + result  # Convert to letter and prepend to result
        n = (n - 1) // 26  # Update n for the next iteration

    return result


def compare_regular_backlog(rows):
    if str(rows.to_dict()['term_name_backlog']) == 'nan':
        rows['grade'] = rows['grade_regular']
        rows['grade_point'] = rows['grade_point_regular']
        rows['total'] = rows['total_regular']
        rows['internal_marks'] = rows['internal_marks_regular']
        rows['external_marks'] = rows['external_marks_regular']
        rows['internal_moderation_marks'] = rows['internal_moderation_marks_regular']
        rows['internal_revaluation_marks'] = rows['internal_revaluation_marks_regular']
        rows['external_moderation_marks'] = rows['external_moderation_marks_regular']
        rows['external_revaluation_marks'] = rows['external_revaluation_marks_regular']
        rows['final_exam_moderation_marks'] = rows['final_exam_moderation_marks_regular']
        rows['max_internal_marks'] = rows['max_internal_marks_regular']
        rows['max_external_marks'] = rows['max_external_marks_regular']
        rows['is_failed'] = rows['is_failed_regular']
        rows['term_name'] = '-'
        rows['unit_point'] = rows['unit_point_regular']
        rows['earned_credit'] = rows['earned_credit_regular']
    else:
        rows['grade'] = rows['grade_backlog']
        rows['grade_point'] = rows['grade_point_backlog']
        rows['total'] = rows['total_backlog']
        rows['internal_marks'] = rows['internal_marks_backlog']
        rows['external_marks'] = rows['external_marks_backlog']
        rows['internal_moderation_marks'] = rows['internal_moderation_marks_backlog']
        rows['internal_revaluation_marks'] = rows['internal_revaluation_marks_backlog']
        rows['external_moderation_marks'] = rows['external_moderation_marks_backlog']
        rows['external_revaluation_marks'] = rows['external_revaluation_marks_backlog']
        rows['final_exam_moderation_marks'] = rows['final_exam_moderation_marks_backlog']
        rows['max_internal_marks'] = rows['max_internal_marks_backlog']
        rows['max_external_marks'] = rows['max_external_marks_backlog']
        rows['is_failed'] = rows['is_failed_backlog']
        rows['term_name'] = 'Backlog (' + str(rows.to_dict()['term_name_backlog']) + ')'
        rows['unit_point'] = rows['unit_point_backlog']
        rows['earned_credit'] = rows['earned_credit_backlog']

    rows['cgpa'] = rows['cgpa_regular']
    rows['sgpa'] = rows['sgpa_regular']
    return rows


# ============================================================================
# DATABASE CONFIG  (creds live here in the script — edit / add tenants as needed)
# ============================================================================
# Keyed by the sub-domain of the instance URL (the text before ".digiicampus.com").
# When the entered instance is not listed here, DEFAULT_DB is used.
TENANT_DB = {
    'mangalayatanjbl': {
        'host': 'collpolldb19-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com',
        'database': 'collpoll_mujbl',
        'user': 'suraj_shetty',
        'password': 'LW3J0MU3mZ',
    },
    # 'cu': {
    #     'host': 'collpolldb9-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com',
    #     'database': 'collpoll_cu',
    #     'user': 'suraj_shetty',
    #     'password': '3qIGaWCdlh',
    # },
    # 'isbr': {
    #     'host': 'digiidb3-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com',
    #     'database': 'collpoll_isbr',
    #     'user': 'suraj_shetty',
    #     'password': 'AdaQwNaEPo',
    # },
}
DEFAULT_DB = TENANT_DB['university']


def get_db_connection(instance_url):
    """Resolve DB creds from the instance sub-domain and open a MySQL connection."""
    tenant_key = instance_url.split('.')[0].lower()
    cfg = TENANT_DB.get(tenant_key, DEFAULT_DB)
    print(f'Connecting to DB: {cfg["database"]} @ {cfg["host"]}')
    return mysql.connector.connect(
        host=cfg['host'], user=cfg['user'],
        password=cfg['password'], database=cfg['database']
    )


def _run_df(conn, query):
    """Execute a SELECT and return the result as a DataFrame."""
    cur = conn.cursor()
    cur.execute(query)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows, columns=cols)


# Per-subject marks are stored as components; tenants name the component types
# differently. This maps a component-type name to the External bucket if it looks
# like an end/external/re-exam component, else Internal. Edit if your Int/Ext
# split comes out wrong for a tenant.
def _int_ext_bucket(component_name):
    name = str(component_name).lower()
    if 'external' in name or 'end-term' in name or 'end term' in name or name == 're-exam':
        return 'External'
    return 'Internal'


# One row per (student, term_course, examination). {WHERE} is swapped for the
# regular vs backlog filters. enrollment_type comes straight from the course
# enrollment record (REGULAR / BACKLOG).
EXAM_GRADE_QUERY = """
SELECT
    eesc.student_ukid,
    esce.type AS enrollment_type,
    coalesce(c.course_code, cv.course_code) AS course_code,
    coalesce(c.course_name, cv.course_name) AS course_name,
    cv.course_credits AS course_credits,
    eesc.term_course_id,
    eesc.examination_id,
    t.name AS term_name,
    t.acad_year_start AS term_start_year,
    t.sequence AS term_sequence,
    ee.name AS examination_name,
    eesc.marks AS total,
    COALESCE(eesc.moderation_grade, eesc.grade) AS grade,
    COALESCE(eesc.moderation_grade_point, eesc.grade_point) AS grade_point,
    eesc.internal_marks AS internal_marks,
    eesc.external_marks AS external_marks,
    eesc.moderation_marks AS final_exam_moderation_marks,
    IF((eesc.is_failed + eesc.is_failed_for_re_exam) >= 1, 'fail', 'pass') AS is_failed,
    IF((eesc.is_failed + eesc.is_failed_for_re_exam) >= 1, 0, cv.course_credits) AS earned_credit,
    IF((eesc.is_failed + eesc.is_failed_for_re_exam) >= 1, 0,
       cv.course_credits * COALESCE(eesc.moderation_grade_point, eesc.grade_point)) AS unit_point
FROM ems_examination_student_course_grade eesc
JOIN ems_examination ee ON ee.id = eesc.examination_id
JOIN term t ON t.id = ee.term_id
JOIN ems_student_programme_enrollment espe
    ON espe.exam_id = eesc.examination_id AND espe.ukid = eesc.student_ukid
JOIN ems_student_course_enrollment esce
    ON esce.student_programme_enrollment_id = espe.id
   AND esce.term_course_id = eesc.term_course_id
JOIN term_course tc ON tc.id = eesc.term_course_id
LEFT JOIN course_version cv ON cv.id = tc.course_version_id
LEFT JOIN course c ON c.course_id = cv.course_id
WHERE {WHERE}
"""


def fetch_component_marks(conn, term_course_ids):
    """Best-effort subject-wise Internal/External marks, moderation and revaluation,
    aggregated from the component-marks table and split by _int_ext_bucket()."""
    cols = ['student_ukid', 'term_course_id', 'internal_marks_comp', 'external_marks_comp',
            'internal_moderation_marks', 'external_moderation_marks',
            'internal_revaluation_marks', 'external_revaluation_marks']
    if not term_course_ids:
        return pd.DataFrame(columns=cols)
    ids = ','.join(str(int(t)) for t in term_course_ids)
    q = f"""
    SELECT eesm.student_ukid, eesm.term_course_id, eect.name AS component_name,
           SUM(eesm.marks) AS marks,
           SUM(eesm.moderation_marks) AS moderation_marks,
           SUM(eesm.revaluation_marks) AS revaluation_marks
    FROM ems_examination_student_marks eesm
    JOIN ems_examination_schema_composition eescon ON eescon.id = eesm.exam_schema_composition_id
    JOIN ems_examination_schema_component eescot ON eescot.id = eescon.schema_component_id
    JOIN ems_examination_component_type eect ON eect.id = eescot.component_type_id
    WHERE eesm.term_course_id IN ({ids})
    GROUP BY eesm.student_ukid, eesm.term_course_id, eect.name
    """
    df = _run_df(conn, q)
    if df.empty:
        return pd.DataFrame(columns=cols)
    for m in ('marks', 'moderation_marks', 'revaluation_marks'):
        df[m] = pd.to_numeric(df[m], errors='coerce')
    df['bucket'] = df['component_name'].apply(_int_ext_bucket)
    agg = df.groupby(['student_ukid', 'term_course_id', 'bucket']).agg(
        marks=('marks', 'sum'),
        moderation=('moderation_marks', 'sum'),
        reval=('revaluation_marks', 'sum')).reset_index()
    out = agg.pivot_table(index=['student_ukid', 'term_course_id'], columns='bucket',
                          values=['marks', 'moderation', 'reval'], aggfunc='sum')
    out.columns = [f'{bucket.lower()}_{metric}' for metric, bucket in out.columns]
    out = out.reset_index().rename(columns={
        'internal_marks': 'internal_marks_comp', 'external_marks': 'external_marks_comp',
        'internal_moderation': 'internal_moderation_marks',
        'external_moderation': 'external_moderation_marks',
        'internal_reval': 'internal_revaluation_marks',
        'external_reval': 'external_revaluation_marks',
    })
    for c in cols:
        if c not in out.columns:
            out[c] = np.nan
    return out[cols]


def fetch_cgpa_sgpa(conn, term_ids):
    """Latest CGPA / SGPA per student across the requested terms' examinations."""
    ids = ','.join(str(int(t)) for t in term_ids)
    q = f"""
    SELECT c.student_ukid, c.exam_id,
           COALESCE(c.re_exam_cgpa, c.cgpa) AS cgpa,
           COALESCE(s.re_exam_sgpa, s.sgpa) AS sgpa
    FROM ems_examination_student_cgpa c
    LEFT JOIN ems_examination_student_sgpa s
        ON s.exam_id = c.exam_id AND s.student_ukid = c.student_ukid
    WHERE c.exam_id IN (SELECT id FROM ems_examination WHERE term_id IN ({ids}))
    """
    df = _run_df(conn, q)
    if df.empty:
        return pd.DataFrame(columns=['student_ukid', 'cgpa', 'sgpa'])
    df = df.sort_values('exam_id').groupby('student_ukid').last().reset_index()
    return df[['student_ukid', 'cgpa', 'sgpa']]


def fetch_exam_data(conn, term_ids):
    """Fetch exam records for the requested home term(s).

    Returns REGULAR rows for courses whose home term is one of term_ids, PLUS
    every BACKLOG attempt by those students (any term the re-exam was conducted
    in). The downstream merge on (ukid, course_code) keeps only backlogs that
    belong to a requested-term course and tags them via their own term_name.
    """
    ids = ','.join(str(int(t)) for t in term_ids)
    reg = _run_df(conn, EXAM_GRADE_QUERY.replace(
        '{WHERE}', f"tc.term_id IN ({ids}) AND esce.type = 'REGULAR'"))
    if reg.empty:
        return reg

    students = reg['student_ukid'].dropna().astype(int).unique().tolist()
    stu_list = ','.join(str(s) for s in students)
    bl = _run_df(conn, EXAM_GRADE_QUERY.replace(
        '{WHERE}', f"esce.type = 'BACKLOG' AND eesc.student_ukid IN ({stu_list})"))

    exam = pd.concat([reg, bl], ignore_index=True)
    exam = exam.drop_duplicates(
        subset=['student_ukid', 'enrollment_type', 'term_course_id', 'examination_id'])

    # subject-wise Internal/External split (marks + moderation + revaluation)
    comp = fetch_component_marks(conn, exam['term_course_id'].dropna().astype(int).unique().tolist())
    exam = exam.merge(comp, on=['student_ukid', 'term_course_id'], how='left')

    # per-course internal/external base marks: prefer the grade row, fall back to
    # the summed component marks (this tenant keeps the split only in components).
    for base, comp_col in (('internal_marks', 'internal_marks_comp'),
                           ('external_marks', 'external_marks_comp')):
        exam[base] = pd.to_numeric(exam[base], errors='coerce').fillna(exam[comp_col])
    exam = exam.drop(columns=['internal_marks_comp', 'external_marks_comp'], errors='ignore')

    # cgpa / sgpa (student-level for the requested terms)
    exam = exam.merge(fetch_cgpa_sgpa(conn, term_ids), on='student_ukid', how='left')

    # columns the report references but that we don't source directly
    exam['max_internal_marks'] = np.nan
    exam['max_external_marks'] = np.nan

    numeric_cols = ['total', 'grade_point', 'course_credits', 'earned_credit', 'unit_point',
                    'final_exam_moderation_marks', 'internal_moderation_marks',
                    'external_moderation_marks', 'internal_revaluation_marks',
                    'external_revaluation_marks', 'cgpa', 'sgpa',
                    'term_start_year', 'term_sequence']
    for col in numeric_cols:
        if col in exam.columns:
            exam[col] = pd.to_numeric(exam[col], errors='coerce')
    return exam


def fetch_user_data(conn, student_ukids):
    """Student master details keyed by ukid (join key for the exam data)."""
    if not student_ukids:
        return pd.DataFrame()
    ids = ','.join(str(int(s)) for s in student_ukids)
    q = f"""
    SELECT
        ua.ukid AS ukid,
        COALESCE(ua.registration_id, sp.application_number) AS registration_id,
        sp.application_number AS application_number,
        sp.year_of_joining AS year_of_joining,
        p.programme_name AS programme_name,
        d.department_name AS department_name,
        NULL AS father_name,
        NULL AS mother_name,
        TRIM(CONCAT_WS(' ', ua.f_name, ua.m_name, ua.l_name)) AS student_name,
        NULL AS current_semester,
        NULL AS current_year,
        sp.gender AS gender
    FROM user_attributes ua
    LEFT JOIN student_profile sp ON sp.ukid = ua.ukid
    LEFT JOIN programme p ON p.programme_id = sp.programme_id
    LEFT JOIN department d ON d.department_id = p.department_id
    WHERE ua.ukid IN ({ids})
    """
    return _run_df(conn, q)


def create_course_header(df, frmt):
    df['course_header'] = df.apply(
        lambda r: setting['course_header'].format(course_code=r['course_code'], course_name=r['course_name'],
                                                  course_credits=r['course_credits']), axis=1)
    return df


def get_instance_name(url):
    req_url = "https://" + url + "/rest/service/collegeConfig?url=" + url

    headers = {
        'accept': 'application/json'
    }

    response = requests.request("GET", req_url, headers=headers, data={})
    if response.status_code == 200:
        return json.loads(response.text)['name']
    else:
        return None


def get_col_widths(dataframe):
    # First we find the maximum length of the index column
    idx_max = max([len(str(s)) for s in dataframe.index.values] + [len(str(dataframe.index.name))])
    # Then, we concatenate this to the max of the lengths of column name and its values for each column, left to right
    return [idx_max] + [max([len(str(s)) for s in dataframe[col].values] + [len(col)]) for col in dataframe.columns]


if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        instance = str(input('Enter complete instance url:\n')) + '.digiicampus.com'

        output_folder_name = instance.split('.')[0].upper() + ' TR Reports'
        instance_name = get_instance_name(instance)
        print(instance_name)

        term_input = input('Enter Term ID(s) for TR Generation (comma-separated):')
        term_ids = [int(x.strip()) for x in term_input.split(',') if x.strip()]

        conn = get_db_connection(instance)
        try:
            exam_data = fetch_exam_data(conn, term_ids)
            if exam_data.empty:
                raise SystemExit('No exam data found for the given term id(s).')
            user_data = fetch_user_data(
                conn, exam_data['student_ukid'].dropna().astype(int).unique().tolist())
        finally:
            conn.close()

        setting = {
            'basic_details': {
                'registration_id': True,
                'student_name': True,
                'application_number': False,
                'year_of_joining': False,
                'programme_name': False,
                'department_name': False,
                'father_name': False,
                'mother_name': False,
                'current_semester': False,
                'current_year': False,
                'gender': False
            },
            'course_header': '{course_name}({course_code})[Credit- {course_credits}]',
            'course_values': {
                'internal_marks': True,
                'internal_moderation_marks': True,
                'internal_revaluation_marks': False,
                'external_marks': True,
                'external_moderation_marks': True,
                'external_revaluation_marks': False,
                'final_exam_moderation_marks': True,
                'total': True,
                'grade': True,
                'grade_point': True,
                'course_credits': True,
                'earned_credit': True,
                'is_failed': True,
                'unit_point': True,
                'term_name': True  # shows "Backlog (<term>)" tag when the course was cleared/attempted as a backlog; "-" otherwise
            },
            'summary': {
                'sgpa': True,
                'cgpa': True,
                'total_marks': True,
                'total_grade': True,
                'total_credit': True,
                'total_earned_credit': True,
                'total_unit_point': True,
                'failed_subject_count': True,
                'remarks_pass_fail': True
            },
            'header': {
                'report_header_font_size': 20,  # DEFAULT: 14
                'report_header_alignment': 'center',  # left/center, DEFAULT: left
            },
            'footer': {
                'report_header_font_size': 14,
                'row1': ['Prepared By/Checked By', 'HOD/Dean', 'Controller Of Examinations'],  # left, middle, right
                'row2': ['Registrar', 'Pro Vice-Chancellor', 'Vice Chancellor'],  # left, middle, right
            }
        }

        # Data is already scoped to the requested term id(s); generate for every
        # home term present in the fetched data.
        termForReport = 'NA'

        data = pd.merge(exam_data, user_data, left_on='student_ukid', right_on='ukid', how='inner').sort_values(
            ['ukid', 'course_code', 'term_start_year', 'term_sequence'])

        # create col for course_header to be used for pivot
        data = create_course_header(data, setting['course_header'])

        # prepare data for final processing
        regular_data = data[data['enrollment_type'] == 'REGULAR'].groupby(
            ['ukid', 'course_code', 'term_name']).first().reset_index()
        backlog_data = data[data['enrollment_type'] == 'BACKLOG'].groupby(['ukid', 'course_code']).last().reset_index()
        final_data = pd.merge(regular_data, backlog_data, how='left', on=['ukid', 'course_code'])

        final_data = final_data[
            ['ukid', 'registration_id_x', 'application_number_x', 'year_of_joining_x', 'programme_name_x',
             'department_name_x', 'father_name_x', 'mother_name_x', 'student_name_x', 'current_semester_x',
             'current_year_x', 'gender_x', 'course_code', 'course_name_x', 'course_credits_x', 'course_header_x',
             'term_start_year_x', 'term_sequence_x',
             'term_name_x', 'examination_name_x', 'grade_x', 'grade_point_x', 'total_x', 'internal_marks_x',
             'internal_moderation_marks_x', 'internal_revaluation_marks_x', 'external_marks_x',
             'external_moderation_marks_x',
             'external_revaluation_marks_x', 'final_exam_moderation_marks_x', 'max_internal_marks_x',
             'max_external_marks_x', 'is_failed_x', 'cgpa_x', 'sgpa_x', 'earned_credit_x',
             'unit_point_x', 'term_name_y', 'examination_name_y', 'grade_y', 'grade_point_y', 'total_y',
             'internal_marks_y', 'internal_moderation_marks_y', 'internal_revaluation_marks_y', 'external_marks_y',
             'external_moderation_marks_y',
             'final_exam_moderation_marks_y', 'external_revaluation_marks_y', 'max_internal_marks_y',
             'max_external_marks_y', 'term_start_year_y', 'term_sequence_y', 'term_name_y',
             'is_failed_y', 'cgpa_y', 'sgpa_y', 'earned_credit_y', 'unit_point_y']]
        final_data.columns = ['ukid', 'registration_id', 'application_number',
                              'year_of_joining', 'programme_name', 'department_name',
                              'father_name', 'mother_name', 'student_name',
                              'current_semester', 'current_year', 'gender', 'course_code',
                              'course_name', 'course_credits', 'course_header', 'term_start_year', 'term_sequence',
                              'term_name_regular', 'examination_name_regular', 'grade_regular', 'grade_point_regular',
                              'total_regular', 'internal_marks_regular', 'internal_moderation_marks_regular',
                              'internal_revaluation_marks_regular', 'external_marks_regular',
                              'external_moderation_marks_regular', 'external_revaluation_marks_regular',
                              'final_exam_moderation_marks_regular',
                              'max_internal_marks_regular', 'max_external_marks_regular',
                              'is_failed_regular', 'cgpa_regular', 'sgpa_regular', 'earned_credit_regular',
                              'unit_point_regular',
                              'term_name_backlog', 'examination_name_backlog', 'grade_backlog', 'grade_point_backlog',
                              'total_backlog',
                              'internal_marks_backlog', 'internal_moderation_marks_backlog',
                              'internal_revaluation_marks_backlog', 'external_marks_backlog',
                              'external_moderation_marks_backlog', 'external_revaluation_marks_backlog',
                              'final_exam_moderation_marks_backlog', 'max_internal_marks_backlog',
                              'max_external_marks_backlog', 'term_start_year_backlog', 'term_sequence_backlog',
                              'term_name_backlog', 'is_failed_backlog', 'cgpa_backlog', 'sgpa_backlog',
                              'earned_credit_backlog', 'unit_point_backlog']

        final_data[['grade', 'grade_point', 'marks', 'internal_marks', 'internal_moderation_marks',
                    'internal_revaluation_marks', 'external_marks',
                    'external_moderation_marks', 'external_revaluation_marks', 'final_exam_moderation_marks',
                    'max_internal_marks', 'max_external_marks', 'is_failed', 'cgpa',
                    'sgpa', 'earned_credit', 'unit_point', 'term_name']] = ''

        final_data = final_data.apply(compare_regular_backlog, axis=1)

        # check if directories exist or create
        downloads_path = str(Path.home() / "Downloads")
        if not os.path.exists(downloads_path + "\\" + output_folder_name):
            os.makedirs(downloads_path + "\\" + output_folder_name)

        # creating iterator based on prog batch and term
        itr = final_data[['programme_name', 'year_of_joining', 'term_name_regular']].drop_duplicates()
        if termForReport != 'NA':
            itr = itr[itr['term_name_regular'] == termForReport]
            term_list = itr['term_name_regular'].drop_duplicates().to_list()
        else:
            term_list = final_data['term_name_regular'].drop_duplicates().to_list()

        for x in term_list:
            # folders are named with colons replaced by spaces; use the same
            # sanitized name for both the existence check and (re)creation.
            term_dir = downloads_path + "\\" + output_folder_name + '\\' + x.replace(':', ' ')
            if os.path.exists(term_dir):
                shutil.rmtree(term_dir, ignore_errors=True)
            os.makedirs(term_dir)

        # breakpoint()
        for index, row in itr.iterrows():
            print(row['term_name_regular'] + ' | ' + row['programme_name'] + ' | ' + str(row['year_of_joining']))
            try:
                temp = final_data[(final_data['programme_name'] == row['programme_name']) &
                                  (final_data['year_of_joining'] == row['year_of_joining']) &
                                  (final_data['term_name_regular'] == row['term_name_regular'])]

                indexCols = [idx for idx in setting['basic_details'].keys() if setting['basic_details'][idx] is True]
                valueCols = [idx for idx in setting['course_values'].keys() if setting['course_values'][idx] is True]
                pivot = temp.pivot(index=['ukid'] + indexCols + ['sgpa', 'cgpa'],
                                   values=valueCols,
                                   columns=['course_header']).swaplevel(0, 1, axis=1).sort_index(axis=1)

                # re-arrage the columns in pivot
                pointer = 0
                newColHead = []
                for course, aggr in pivot.columns:
                    newColHead.append((course, list(valueCols)[pointer]))
                    if pointer + 1 == len(valueCols):
                        pointer = 0
                    else:
                        pointer = pointer + 1

                pivot = pivot[newColHead]
                pivot.reset_index(inplace=True)

                regId = pivot["registration_id"].drop_duplicates().to_list()

                statuslst = []
                totalGrade = []
                totalMarks = []
                totalUnitPoint = []
                totalCredits = []
                earnedCredits = []
                pass_statuslst = []

                for registrationId in regId:
                    ref = temp[temp["registration_id"] == registrationId]
                    pass_status = ""
                    fail_course = 0
                    grades = sum(ref['grade_point'])
                    sumMarks = sum(ref['total'])
                    sumUnitPoint = sum(ref['unit_point'])
                    sumCredits = sum(ref['course_credits'])
                    sumEarnedCredits = sum(ref['earned_credit'])

                    for i, r in ref.iterrows():
                        if r["is_failed"] == "fail":
                            fail_course = 1 + fail_course
                            string = r["course_code"]
                            pass_status = "(" + string + ")" + pass_status

                    pass_statuslst.append(pass_status)
                    statuslst.append(fail_course)
                    totalGrade.append(grades)
                    totalMarks.append(sumMarks)
                    totalUnitPoint.append(sumUnitPoint)
                    totalCredits.append(sumCredits)
                    earnedCredits.append(sumEarnedCredits)

                if setting['summary']['total_marks'] is True:
                    pivot['total_marks'] = totalMarks

                if setting['summary']['total_grade'] is True:
                    pivot["total_grade"] = totalGrade

                if setting['summary']['total_credit'] is True:
                    pivot["total_credit"] = totalCredits

                if setting['summary']['total_earned_credit'] is True:
                    pivot['total_earned_credit'] = earnedCredits

                if setting['summary']['total_unit_point'] is True:
                    pivot["total_unit_point"] = totalUnitPoint

                if setting['summary']['failed_subject_count'] is True:
                    pivot["failed_subject_count"] = statuslst
                    pivot["failed_subject_count"] = pivot["failed_subject_count"].replace([''], '0')

                if setting['summary']['remarks_pass_fail'] is True:
                    pivot['remarks'] = pass_statuslst
                    pivot["remarks"] = pivot["remarks"].replace([''], 'Pass')

                # previous terms summary
                temp2 = final_data[
                    (final_data['programme_name'] == row['programme_name']) & (
                            final_data['year_of_joining'] == row['year_of_joining'])] \
                    .groupby(['ukid', 'term_name_regular', 'term_start_year', 'term_sequence']).agg({
                    'course_credits': 'sum',
                    'earned_credit': 'sum',
                    'unit_point': 'sum'
                }).reset_index()
                temp2['key'] = temp2['term_start_year'].astype(str) + '-' + temp2['term_sequence'].astype(str)
                summary_filter_till_current_sem = temp2[
                    temp2['key'] <= str(temp['term_start_year'].drop_duplicates().to_list()[0]) + '-' + str(
                        temp['term_sequence'].drop_duplicates().to_list()[0])]
                summary_till_current_sem = summary_filter_till_current_sem.sort_values(['key']).groupby(
                    ['ukid']).agg(
                    {'course_credits': 'sum', 'earned_credit': 'sum', 'unit_point': 'sum'})

                # get the start to end term for col name for current sem
                current_term_lst = summary_filter_till_current_sem.sort_values(['key'])[
                    'term_name_regular'].drop_duplicates().to_list()
                if len(current_term_lst) > 1:
                    current_col_head = current_term_lst[0] + ' - ' + current_term_lst[len(current_term_lst) - 1]
                else:
                    current_col_head = current_term_lst[0]

                summary_till_current_sem.columns = [([current_col_head] * len(summary_till_current_sem.columns)),
                                                    summary_till_current_sem.columns]
                summary_till_current_sem = summary_till_current_sem.reset_index()

                # filter data till previous semester
                summary_filter_till_previous_sem = temp2[
                    temp2['key'] < str(temp['term_start_year'].drop_duplicates().to_list()[0]) + '-' + str(
                        temp['term_sequence'].drop_duplicates().to_list()[0])]
                summary_till_previous_sem = summary_filter_till_previous_sem.sort_values(['key']).groupby(
                    ['ukid']).agg(
                    {'course_credits': 'sum', 'earned_credit': 'sum', 'unit_point': 'sum'})

                # get the start to end term for col name for previous sem
                prev_term_lst = summary_filter_till_previous_sem.sort_values(['key'])[
                    'term_name_regular'].drop_duplicates().to_list()
                if len(prev_term_lst) > 0:
                    if len(prev_term_lst) > 1:
                        prev_col_head = prev_term_lst[0] + ' - ' + prev_term_lst[len(prev_term_lst) - 1]
                    elif len(prev_term_lst) == 1:
                        prev_col_head = prev_term_lst[0]

                    summary_till_previous_sem.columns = [([prev_col_head] * len(summary_till_previous_sem.columns)),
                                                         summary_till_previous_sem.columns]
                    summary_till_previous_sem = summary_till_previous_sem.reset_index()

                    final = pd.merge(pivot, summary_till_previous_sem, on='ukid', how='left')
                    final = pd.merge(final, summary_till_current_sem, on='ukid', how='left')
                else:
                    final = pd.merge(pivot, summary_till_current_sem, on='ukid', how='left')

                no_of_cols_pivot = len(final.columns)

                # Define Excel Writer
                fileName = row['programme_name'] + '-' + str(row['year_of_joining'])
                term_name_safe = row["term_name_regular"].replace(':', ' ')  # Replace colons with spaces
                writer = pd.ExcelWriter(
                    str(Path.home() / f'Downloads/{output_folder_name}/{term_name_safe}/{fileName}.xlsx'))

                # Main Table to Excel
                final.index = final.index + 1
                final.to_excel(writer, sheet_name='Sheet1', index=True, startrow=7)

                # Dynamic adjust Column Width of pivot
                try:
                    for column in final:
                        column_width = max(final[column].astype(str).map(len).max(), len(column))
                        col_idx = final.columns.get_loc(column)
                        writer.sheets['Sheet1'].set_column(col_idx, col_idx, column_width)
                except ValueError:
                    pass

                # Define sheet headers
                workbook = writer.book
                worksheet = writer.sheets['Sheet1']

                header_alignment_col_idx = int(pivot.shape[1] / 2) if setting['header'][
                                                                          'report_header_alignment'] == 'center' else 0
                headerSize = setting['header']['report_header_font_size']

                # write header details
                worksheet.merge_range('A1:' + number_to_alphabet(pivot.shape[1] + 1).upper() + '1', instance_name,
                                      workbook.add_format(
                                          {'align': 'center', 'bold': True, 'color': '#000234', 'size': headerSize}))
                worksheet.merge_range('A2:' + number_to_alphabet(pivot.shape[1] + 1).upper() + '2',
                                      'Programme - ' + row['programme_name'],
                                      workbook.add_format(
                                          {'align': 'center', 'bold': True, 'color': '#000234', 'size': headerSize}))
                worksheet.merge_range('A3:' + number_to_alphabet(pivot.shape[1] + 1).upper() + '3',
                                      'Batch Year - ' + str(row['year_of_joining']),
                                      workbook.add_format(
                                          {'align': 'center', 'bold': True, 'color': '#000234', 'size': headerSize}))
                worksheet.merge_range('A4:' + number_to_alphabet(pivot.shape[1] + 1).upper() + '4',
                                      'Term - ' + row['term_name_regular'],
                                      workbook.add_format(
                                          {'align': 'center', 'bold': True, 'color': '#000234', 'size': headerSize}))
                worksheet.merge_range('A5:' + number_to_alphabet(pivot.shape[1] + 1).upper() + '5', 'Session - ',
                                      workbook.add_format(
                                          {'align': 'center', 'bold': True, 'color': '#000234', 'size': headerSize}))

                # define sheet footers
                footer_left_idx = 0
                footer_mid_idx = int(pivot.shape[1] / 2)
                footer_right_idx = pivot.shape[1] + 1

                footer_start_row = 7 + pivot.shape[0] + 8  # 7rows left before pivot table and 8rows after pivot

                # write footer details
                # row1
                if setting['footer']['row1'][0] != '-':
                    worksheet.write(footer_start_row, footer_left_idx, setting['footer']['row1'][0],
                                    workbook.add_format({'bold': True, 'color': '#000234',
                                                         'size': setting['footer']['report_header_font_size']}))

                if setting['footer']['row1'][1] != '-':
                    worksheet.write(footer_start_row, footer_mid_idx, setting['footer']['row1'][1],
                                    workbook.add_format({'bold': True, 'color': '#000234',
                                                         'size': setting['footer']['report_header_font_size']}))

                if setting['footer']['row1'][2] != '-':
                    worksheet.write(footer_start_row, footer_right_idx, setting['footer']['row1'][2],
                                    workbook.add_format({'bold': True, 'color': '#000234',
                                                         'size': setting['footer']['report_header_font_size']}))

                # row2
                if setting['footer']['row2'][0] != '-':
                    worksheet.write(footer_start_row + 5, footer_left_idx, setting['footer']['row2'][0],
                                    workbook.add_format({'bold': True, 'color': '#000234',
                                                         'size': setting['footer']['report_header_font_size']}))

                if setting['footer']['row2'][1] != '-':
                    worksheet.write(footer_start_row + 5, footer_mid_idx, setting['footer']['row2'][1],
                                    workbook.add_format({'bold': True, 'color': '#000234',
                                                         'size': setting['footer']['report_header_font_size']}))

                if setting['footer']['row2'][2] != '-':
                    worksheet.write(footer_start_row + 5, footer_right_idx, setting['footer']['row2'][2],
                                    workbook.add_format({'bold': True, 'color': '#000234',
                                                         'size': setting['footer']['report_header_font_size']}))

                # Apply borders
                border_fmt = workbook.add_format({'bottom': 4, 'top': 4, 'left': 4, 'right': 4})
                worksheet.conditional_format(xlsxwriter.utility.xl_range(8, 0, len(final) + 9, len(final.columns) + 1),
                                             {'type': 'no_errors', 'format': border_fmt})

                try:
                    for i, width in enumerate(get_col_widths(final)):
                        worksheet.set_column(i, i, width)
                except ValueError:
                    pass

                writer.close()
                print('\tReport Generated')
            except OSError as e:
                print(f'\tFailed to save file: {e}')
            except Exception as e:
                print(f'\tSome Error Occured: {e}')
