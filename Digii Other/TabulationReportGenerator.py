import pandas as pd
import numpy as np
import xlsxwriter
from pathlib import Path
import os
import sys
import warnings
from datetime import datetime
import pymysql
from dotenv import load_dotenv
from helper import connect_to_tenant_database

def fetch_user_data(connection, STUDENT_UKIDS): # runs the user data query
    query = f"""
    SELECT 
        ua.ukid as student_ukid,
        CASE
            WHEN ua.registration_id IS NULL THEN sp.application_number ELSE ua.registration_id
        END as registration_id,
        CONCAT(ua.f_name," ",ua.m_name," ",ua.l_name) as student_name,
        sp.year_of_joining,
        p.programme_name,
        ua.user_type
    FROM
        user_attributes ua
    LEFT JOIN student_profile sp ON sp.ukid = ua.ukid
    LEFT JOIN programme p ON p.programme_id = sp.programme_id 
    WHERE
        user_type = 'student'
        AND ua.ukid IN ({STUDENT_UKIDS});
    """
    cursor = connection.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    user_df = pd.DataFrame(rows, columns=columns)
    return user_df

def fetch_course_grades_data(connection, EXAM_IDS): # runs the course grades query
    query = f"""
    SELECT
        eesc.student_ukid,
        e.name as examination_name,
        e.id as exam_id,
        t.id as term_id,
        t.name as term_name,
        tc.course_id,
        tc.course_name,
        tc.course_code,
        IF(eesc.moderation_grade IS NULL, eesc.grade, eesc.moderation_grade) AS grade,
        IF(eesc.moderation_grade_point IS NULL, eesc.grade_point, eesc.moderation_grade_point) AS grade_point,
        tc.course_credits,
        eesc.marks as total_marks,
        IF(eesc.grade IS NULL, '-', IF(eesc.is_failed + eesc.is_failed_for_re_exam >= 1, 'Fail', 'Pass')) AS is_failed,
        IF(eesc.is_failed + eesc.is_failed_for_re_exam >= 1, 0, tc.course_credits) AS earned_credit,
        IF(eesc.is_failed + eesc.is_failed_for_re_exam >= 1, 0, tc.course_credits * eesc.grade_point) AS unit_point
    FROM
        ems_examination_student_course_grade eesc
    LEFT JOIN term_course tc ON tc.id = eesc.term_course_id
    LEFT JOIN ems_examination e ON e.id = eesc.examination_id
    LEFT JOIN term t ON t.id = e.term_id
    WHERE eesc.examination_id IN ({EXAM_IDS})
    """
    cursor = connection.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    course_grades_df = pd.DataFrame(rows, columns=columns)
    return course_grades_df

def fetch_assessment_marks_data(connection, TERM_IDS): # runs the assessment marks query
    query = f"""
    SELECT
        eesm.student_ukid,
        tc.term_id,
        tc.course_name,
        tc.course_id,
        eect.name as component_name,
        eect.type as component_type,
        eescon.exam_type_label as assessment_name,
        eescon.maximum_marks as assessment_maximum_marks,
        eesm.marks as assessment_obtained_marks,
        eesm.moderation_marks as assesment_moderation_marks,
        eesm.revaluation_marks as assessment_revaluation_marks
    FROM
        ems_examination_student_marks eesm
    LEFT JOIN ems_examination_schema_composition eescon ON eescon.id = eesm.exam_schema_composition_id
    LEFT JOIN ems_examination_schema_component eescot ON eescot.id = eescon.schema_component_id
    LEFT JOIN ems_examination_component_type eect ON eect.id = eescot.component_type_id
    LEFT JOIN term_course tc ON eesm.term_course_id = tc.id
    WHERE tc.term_id IN ({TERM_IDS})
    """
    cursor = connection.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    assessment_marks_df = pd.DataFrame(rows, columns=columns)
    return assessment_marks_df

def fetch_cgpa_sgpa_data(connection, EXAM_IDS): # runs the cgpa and sgpa query
    query = f"""
    SELECT
        t1.student_ukid,
        t1.exam_id,
        COALESCE(t1.re_exam_cgpa, t1.cgpa) as cgpa,
        COALESCE(t2.re_exam_sgpa, t2.sgpa) as sgpa
    FROM ems_examination_student_cgpa t1
    LEFT JOIN ems_examination_student_sgpa t2 ON t1.exam_id = t2.exam_id AND t1.student_ukid = t2.student_ukid
    WHERE t1.exam_id IN ({EXAM_IDS})
    """
    cursor = connection.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    cgpa_sgpa_df = pd.DataFrame(rows, columns=columns)
    return cgpa_sgpa_df

def fetch_summary_columns(course_grades_df): # calculates summary columns based on dataframe from course grades query
    if course_grades_df.empty:
        return pd.DataFrame(columns=['student_ukid', 'total_grade', 'total_credits', 'total_earned_credits', 'total_unit_point', 'failed_subject_count'])
    
    summary = course_grades_df.groupby('student_ukid').agg({
        'grade_point': 'sum',
        'course_credits': 'sum',
        'earned_credit': 'sum',
        'unit_point': 'sum',
        'is_failed': lambda x: (x == 'Fail').sum()
    }).reset_index()

    summary = summary.rename(columns={
        'grade_point': 'total_grade',
        'course_credits': 'total_credits',
        'earned_credit': 'total_earned_credits',
        'unit_point': 'total_unit_point',
        'is_failed': 'failed_subject_count'
    })
    return summary

def course_code_name_merge(course_grades_df): # creates topmost layer of pivot table that stores course name and course code as course_header
    if 'course_name' in course_grades_df.columns and 'course_code' in course_grades_df.columns:
        course_grades_df['course_header'] = course_grades_df.apply(
            lambda r: f"{r['course_name'] if pd.notna(r['course_name']) else ''}[{r['course_code'] if pd.notna(r['course_code']) else ''}]", 
            axis=1
        )
    return course_grades_df

def merging_dataframes_for_pivot(user_df,course_grades_df,assessment_marks_df,cgpa_sgpa_df,summary_df): # merges all dataframes on student_ukid for pivot table
    merged_df = user_df.copy()
    merged_df = merged_df.merge(course_grades_df, on='student_ukid', how='inner', suffixes=('', '_course_grades'))
    merged_df = merged_df.merge(assessment_marks_df, on=['student_ukid','term_id','course_id'], how='inner', suffixes=('', '_assessment_marks'))
    
    # Fix: Check if cgpa_sgpa_df is empty or missing required columns before merging
    if not cgpa_sgpa_df.empty and 'student_ukid' in cgpa_sgpa_df.columns and 'exam_id' in cgpa_sgpa_df.columns:
        merged_df = merged_df.merge(cgpa_sgpa_df, on=['student_ukid','exam_id'], how='left', suffixes=('', '_cgpa_sgpa'))
    else:
        # If cgpa_sgpa_df is empty or missing columns, add empty cgpa/sgpa columns
        merged_df['cgpa'] = None
        merged_df['sgpa'] = None
        print("  Warning: CGPA/SGPA data is empty or missing required columns. Setting cgpa and sgpa to None.")
    
    merged_df = merged_df.merge(summary_df, on='student_ukid', how='inner', suffixes=('', '_summary'))
    return merged_df

def prepare_pivot_data(merged_df): # prepares data structure for pivot table

    def convert_to_int(value): # converts column values to integers, preserving NaN
        try:
            if pd.isna(value):
                return np.nan
            return int(float(value))
        except (ValueError, TypeError):
            return np.nan

    data = course_code_name_merge(merged_df) # creates course_header column
    data['component_name'] = data['component_name']
    data['assessment_name'] = data['assessment_name']
    data['assessment_maximum_marks'] = data['assessment_maximum_marks'].apply(convert_to_int)
    data['assessment_obtained_marks'] = data['assessment_obtained_marks'].apply(convert_to_int)
    
    # Handle assessment_moderation_marks - check if column exists and preserve NaN
    if 'assessment_moderation_marks' in data.columns:
        data['assessment_moderation_marks'] = data['assessment_moderation_marks'].apply(convert_to_int)
    else:
        data['assessment_moderation_marks'] = np.nan
    
    # Handle assessment_revaluation_marks - preserve NaN if column exists
    if 'assessment_revaluation_marks' in data.columns:
        data['assessment_revaluation_marks'] = data['assessment_revaluation_marks'].apply(convert_to_int)
    else:
        data['assessment_revaluation_marks'] = np.nan
    
    return data
def number_to_alphabet(n): # converts number to excel column letter - required for excel ordering    
    if n <= 0:
        return "Invalid input"
    result = ""
    while n > 0:
        remainder = (n - 1) % 26
        result = chr(remainder + ord('A')) + result
        n = (n - 1) // 26
    return result

def get_col_widths(dataframe): # calculates column widths for Excel > have used this in generate_excel_report function > idx max is the maximum length of words by unit alphabets for column length
    idx_max = max([len(str(s)) for s in dataframe.index.values] + [len(str(dataframe.index.name)) if dataframe.index.name else 0])
    return [idx_max] + [max([len(str(s)) for s in dataframe[col].values] + [len(col) if isinstance(col, str) else len(str(col))]) for col in dataframe.columns]

def create_pivot_tables(data): # creates pivot tables for obtained, moderation, re-evaluation, and maximum marks - transforms long format to wide format
    indexCols = ['registration_id', 'student_name'] # columns that will be index rows in pivot
    
    # deduplication just to be on the safer side of things
    data_dedup = data.drop_duplicates(
        subset=['student_ukid'] + indexCols + ['sgpa', 'cgpa', 'course_header', 'component_name', 'assessment_name'],
        keep='first'
    )
    
    # create pivot for obtained marks - students as rows, course/component/assessment as header columns
    try:
        pivot_obtained = data_dedup.pivot_table(
            index=['student_ukid'] + indexCols + ['sgpa', 'cgpa'],
            values='assessment_obtained_marks',
            columns=['course_header', 'component_name', 'assessment_name'],
            aggfunc='first',
            fill_value=np.nan
        )
        if pivot_obtained.columns.duplicated().any():
            pivot_obtained = pivot_obtained.loc[:, ~pivot_obtained.columns.duplicated()]
    except Exception as e:
        print(f"Error creating pivot_obtained: {e}")
        raise
    
    # create pivot column for moderation marks
    try:
        pivot_moderation = data_dedup.pivot_table(
            index=['student_ukid'] + indexCols + ['sgpa', 'cgpa'],
            values='assessment_moderation_marks',
            columns=['course_header', 'component_name', 'assessment_name'],
            aggfunc='first',
            fill_value=np.nan
        )
        if pivot_moderation.columns.duplicated().any():
            pivot_moderation = pivot_moderation.loc[:, ~pivot_moderation.columns.duplicated()]
    except Exception as e:
        print(f"Error creating pivot_moderation: {e}")
        raise
    
    # create pivot column for re-evaluation marks
    try:
        pivot_reevaluation = data_dedup.pivot_table(
            index=['student_ukid'] + indexCols + ['sgpa', 'cgpa'],
            values='assessment_revaluation_marks',
            columns=['course_header', 'component_name', 'assessment_name'],
            aggfunc='first',
            fill_value=np.nan
        )
        if pivot_reevaluation.columns.duplicated().any():
            pivot_reevaluation = pivot_reevaluation.loc[:, ~pivot_reevaluation.columns.duplicated()]
    except Exception as e:
        print(f"Error creating pivot_reevaluation: {e}")
        raise
    
    # create pivot column for maximum marks
    try:
        pivot_maximum = data_dedup.pivot_table(
            index=['student_ukid'] + indexCols + ['sgpa', 'cgpa'],
            values='assessment_maximum_marks',
            columns=['course_header', 'component_name', 'assessment_name'],
            aggfunc='first',
            fill_value=np.nan
        )
        if pivot_maximum.columns.duplicated().any():
            pivot_maximum = pivot_maximum.loc[:, ~pivot_maximum.columns.duplicated()]
    except Exception as e:
        print(f"Error creating pivot_maximum: {e}")
        raise
    
    # ensure all pivots have same systematic order for later mering
    if not pivot_moderation.index.equals(pivot_obtained.index):
        pivot_moderation = pivot_moderation.reindex(pivot_obtained.index, fill_value=np.nan)
    if not pivot_reevaluation.index.equals(pivot_obtained.index):
        pivot_reevaluation = pivot_reevaluation.reindex(pivot_obtained.index, fill_value=np.nan)
    if not pivot_maximum.index.equals(pivot_obtained.index):
        pivot_maximum = pivot_maximum.reindex(pivot_obtained.index, fill_value=np.nan)
    
    return pivot_obtained, pivot_moderation, pivot_reevaluation, pivot_maximum, data_dedup

def build_combined_pivot(pivot_obtained, pivot_moderation, pivot_reevaluation, pivot_maximum, course_order, course_grades_df): # combines all 4 pivot tables into one with columns for each mark type like obtained, moderatd, re-evaluation, maximum
    pivot = pd.DataFrame(index=pivot_obtained.index) # start with empty dataframe with same index
    
    new_columns = []
    # iterate through courses and create column names for all mark types mentioned above
    for course in course_order:
        if course in pivot_obtained.columns.get_level_values(0):
            course_cols = [col for col in pivot_obtained.columns if col[0] == course]
            
            # group assessments by component name for which assessment falls under which component
            component_groups = {}
            for col in course_cols:
                comp_name = col[1]
                assessment = col[2]
                if comp_name not in component_groups:
                    component_groups[comp_name] = []
                if assessment not in component_groups[comp_name]:
                    component_groups[comp_name].append(assessment)
            
            # create column names for each assessment: Marks, Moderation Marks, Re-evaluation Marks, Maximum Marks
            for comp_name in sorted(component_groups.keys()):
                for assessment in sorted(component_groups[comp_name]):
                    assessment_formatted = str(assessment).replace(' ', '')
                    
                    # all assessment names + marks columns are created below
                    marks_col = (course, comp_name, f"{assessment_formatted} Marks")
                    moderation_col = (course, comp_name, f"{assessment_formatted} Moderation Marks")
                    reevaluation_col = (course, comp_name, f"{assessment_formatted} Re-evaluation Marks")
                    max_col = (course, comp_name, f"{assessment_formatted} Maximum Marks")
                    
                    # handle duplicate column names by appending counter
                    counter = 1
                    while marks_col in new_columns:
                        marks_col = (course, comp_name, f"{assessment_formatted} Marks_{counter}")
                        counter += 1
                    new_columns.append(marks_col)
                    
                    counter = 1
                    while moderation_col in new_columns:
                        moderation_col = (course, comp_name, f"{assessment_formatted} Moderation Marks_{counter}")
                        counter += 1
                    new_columns.append(moderation_col)
                    
                    counter = 1
                    while reevaluation_col in new_columns:
                        reevaluation_col = (course, comp_name, f"{assessment_formatted} Re-evaluation Marks_{counter}")
                        counter += 1
                    new_columns.append(reevaluation_col)
                    
                    counter = 1
                    while max_col in new_columns:
                        max_col = (course, comp_name, f"{assessment_formatted} Maximum Marks_{counter}")
                        counter += 1
                    new_columns.append(max_col)
            
            # Add course-level grade columns after all assessments for each course
            # Use empty string for component level to avoid double header
            grade_cols = [
                (course, '', 'Grade'),
                (course, '', 'Grade Point'),
                (course, '', 'Course Credits'),
                (course, '', 'Earned Credits'),
                (course, '', 'is_failed'),
                (course, '', 'Unit Point')
            ]
            
            for grade_col in grade_cols:
                if grade_col not in new_columns:
                    new_columns.append(grade_col)
    
    def safe_int_convert(value):
        try:
            if pd.isna(value):
                return np.nan
            return int(float(value))
        except (ValueError, TypeError):
            return np.nan
    
    # Create a mapping from course_header to course data for quick lookup
    # First ensure course_header exists in course_grades_df
    if 'course_header' not in course_grades_df.columns:
        course_grades_df = course_code_name_merge(course_grades_df.copy())
    
    course_data_map = {}
    if not course_grades_df.empty:
        for idx, row in course_grades_df.iterrows():
            course_header = row.get('course_header', '')
            if not course_header:
                course_name = row['course_name'] if pd.notna(row.get('course_name')) else ''
                course_code = row['course_code'] if pd.notna(row.get('course_code')) else ''
                course_header = f"{course_name}[{course_code}]"
            
            if course_header not in course_data_map:
                course_data_map[course_header] = {}
            
            student_ukid = row['student_ukid']
            if student_ukid not in course_data_map[course_header]:
                course_data_map[course_header][student_ukid] = {
                    'grade': row.get('grade', '') if pd.notna(row.get('grade')) else '',
                    'grade_point': safe_int_convert(row.get('grade_point', 0)),
                    'course_credits': safe_int_convert(row.get('course_credits', 0)),
                    'earned_credit': safe_int_convert(row.get('earned_credit', 0)),
                    'is_failed': row.get('is_failed', '') if pd.notna(row.get('is_failed')) else '',
                    'unit_point': safe_int_convert(row.get('unit_point', 0))
                }
    
    # fill pivot with data from previously created source pivot table based on column name
    for new_col in new_columns:
        course, comp_name, col_name = new_col
        
        if col_name == 'Grade' and comp_name == '':
            # Grade column (course-level)
            pivot[new_col] = ''
            if course in course_data_map:
                for idx in pivot.index:
                    student_ukid = idx if not isinstance(pivot.index, pd.MultiIndex) else idx[0]
                    if student_ukid in course_data_map[course]:
                        pivot.at[idx, new_col] = course_data_map[course][student_ukid]['grade']
        elif col_name == 'Grade Point' and comp_name == '':
            # Grade Point column (course-level)
            pivot[new_col] = np.nan
            if course in course_data_map:
                for idx in pivot.index:
                    student_ukid = idx if not isinstance(pivot.index, pd.MultiIndex) else idx[0]
                    if student_ukid in course_data_map[course]:
                        pivot.at[idx, new_col] = course_data_map[course][student_ukid]['grade_point']
        elif col_name == 'Course Credits' and comp_name == '':
            # Course Credits column (course-level)
            pivot[new_col] = np.nan
            if course in course_data_map:
                for idx in pivot.index:
                    student_ukid = idx if not isinstance(pivot.index, pd.MultiIndex) else idx[0]
                    if student_ukid in course_data_map[course]:
                        pivot.at[idx, new_col] = course_data_map[course][student_ukid]['course_credits']
        elif col_name == 'Earned Credits' and comp_name == '':
            # Earned Credits column (course-level)
            pivot[new_col] = np.nan
            if course in course_data_map:
                for idx in pivot.index:
                    student_ukid = idx if not isinstance(pivot.index, pd.MultiIndex) else idx[0]
                    if student_ukid in course_data_map[course]:
                        pivot.at[idx, new_col] = course_data_map[course][student_ukid]['earned_credit']
        elif col_name == 'is_failed' and comp_name == '':
            # is_failed column (course-level)
            pivot[new_col] = ''
            if course in course_data_map:
                for idx in pivot.index:
                    student_ukid = idx if not isinstance(pivot.index, pd.MultiIndex) else idx[0]
                    if student_ukid in course_data_map[course]:
                        pivot.at[idx, new_col] = course_data_map[course][student_ukid]['is_failed']
        elif col_name == 'Unit Point' and comp_name == '':
            # Unit Point column (course-level)
            pivot[new_col] = np.nan
            if course in course_data_map:
                for idx in pivot.index:
                    student_ukid = idx if not isinstance(pivot.index, pd.MultiIndex) else idx[0]
                    if student_ukid in course_data_map[course]:
                        pivot.at[idx, new_col] = course_data_map[course][student_ukid]['unit_point']
        elif 'Maximum Marks' in col_name:
            # get data from pivot_maximum for max marks
            assessment_name = col_name.replace(' Maximum Marks', '').replace(' ', '')
            orig_col = None
            for orig in pivot_maximum.columns:
                if (orig[0] == course and orig[1] == comp_name and 
                    str(orig[2]).replace(' ', '') == assessment_name):
                    orig_col = orig
                    break
            if orig_col and orig_col in pivot_maximum.columns:
                pivot[new_col] = pivot_maximum[orig_col].replace(0, np.nan)
            else:
                pivot[new_col] = np.nan
        elif 'Moderation Marks' in col_name:
            # get data from pivot_moderation for moderation marks
            assessment_name = col_name.replace(' Moderation Marks', '').replace(' ', '')
            orig_col = None
            for orig in pivot_moderation.columns:
                if (orig[0] == course and orig[1] == comp_name and 
                    str(orig[2]).replace(' ', '') == assessment_name):
                    orig_col = orig
                    break
            if orig_col and orig_col in pivot_moderation.columns:
                pivot[new_col] = pivot_moderation[orig_col].replace(0, np.nan)
            else:
                pivot[new_col] = np.nan
        elif 'Re-evaluation Marks' in col_name:
            # get data from pivot_reevaluation fir reval marks
            assessment_name = col_name.replace(' Re-evaluation Marks', '').replace(' ', '')
            orig_col = None
            for orig in pivot_reevaluation.columns:
                if (orig[0] == course and orig[1] == comp_name and 
                    str(orig[2]).replace(' ', '') == assessment_name):
                    orig_col = orig
                    break
            if orig_col and orig_col in pivot_reevaluation.columns:
                pivot[new_col] = pivot_reevaluation[orig_col].replace(0, np.nan)
            else:
                pivot[new_col] = np.nan
        else:
            # get data from pivot_obtained for obtained marks
            assessment_name = col_name.replace(' Marks', '').replace(' ', '')
            orig_col = None
            for orig in pivot_obtained.columns:
                if (orig[0] == course and orig[1] == comp_name and 
                    str(orig[2]).replace(' ', '') == assessment_name):
                    orig_col = orig
                    break
            if orig_col and orig_col in pivot_obtained.columns:
                pivot[new_col] = pivot_obtained[orig_col].replace(0, np.nan)
            else:
                pivot[new_col] = np.nan
    
    # remove duplicate columns if any to be on safer side
    if pivot.columns.duplicated().any():
        seen = set()
        unique_cols = []
        for col in pivot.columns:
            if col not in seen:
                seen.add(col)
                unique_cols.append(col)
        pivot = pivot[unique_cols]
    
    return pivot

def add_summary_columns(pivot_df, data, course_grades_df, summary_df): # adds course-level summary columns (Total, Grade, etc.) and overall student summary stats
    pivot = pivot_df.copy()
    
    # get course order from data
    course_order = []
    if 'course_header' in data.columns:
        for course in data['course_header'].unique():
            if course in pivot.columns.get_level_values(0):
                course_order.append(course)
    
    # create empty summary columns for each course (Total, Grade, Grade Point, etc.) > last few cols
    summary_columns = []
    for course in course_order:
        course_data = data[data['course_header'] == course]
        
        summary_cols = [
            ('Total', 'Total', 'numeric'),
            ('Grade', 'Grade', 'text'),
            ('Grade Point', 'Grade Point', 'numeric'),
            ('Course Credits', 'Course Credits', 'numeric'),
            ('Earned Credits', 'Earned Credits', 'numeric'),
            ('is_failed', 'is_failed', 'text'),
            ('Unit Point', 'Unit Point', 'numeric')
        ]
        
        for col_name, col_label, col_type in summary_cols:
            col_tuple = (course, col_name, col_label)
            if col_tuple not in pivot.columns:
                summary_columns.append(col_tuple)
                # Initialize numeric columns as NaN, text columns as empty string
                if col_type == 'numeric':
                    pivot[col_tuple] = np.nan
                else:
                    pivot[col_tuple] = ''
    
    # get list of registration IDs to iterate through
    if isinstance(pivot.index, pd.MultiIndex):
        if 'registration_id' in pivot.index.names:
            regId = pivot.index.get_level_values('registration_id').unique().tolist()
        else:
            regId = data['registration_id'].drop_duplicates().to_list()
    else:
        if 'registration_id' in pivot.columns:
            regId = pivot["registration_id"].drop_duplicates().to_list()
        else:
            regId = data['registration_id'].drop_duplicates().to_list()
    
    def safe_int_convert(value):
        try:
            if pd.isna(value):
                return np.nan
            return int(float(value))
        except (ValueError, TypeError):
            return np.nan
    
    # fill course-level summary columns for each student
    for registrationId in regId:
        if isinstance(pivot.index, pd.MultiIndex):
            if 'registration_id' in pivot.index.names:
                student_rows = pivot[pivot.index.get_level_values('registration_id') == registrationId]
                if student_rows.empty:
                    continue
                student_ukid = student_rows.index.get_level_values('student_ukid')[0]
            else:
                student_data = data[data['registration_id'] == registrationId]
                if student_data.empty:
                    continue
                student_ukid = student_data['student_ukid'].iloc[0]
        else:
            if 'registration_id' in pivot.columns:
                student_rows = pivot[pivot['registration_id'] == registrationId]
                if student_rows.empty:
                    continue
                student_ukid = student_rows['student_ukid'].iloc[0] if 'student_ukid' in pivot.columns else None
            else:
                student_data = data[data['registration_id'] == registrationId]
                if student_data.empty:
                    continue
                student_ukid = student_data['student_ukid'].iloc[0]
        
        if student_ukid is None:
            continue
        
        # get course data for student being looked up student and fill summary columns
        student_courses = course_grades_df[course_grades_df['student_ukid'] == student_ukid]
        
        for _, course_row in student_courses.iterrows():
            # Use course_header from course_grades_df if available, otherwise construct it
            if 'course_header' in course_row and pd.notna(course_row.get('course_header')):
                course_header = course_row['course_header']
            else:
                course_name = course_row['course_name'] if pd.notna(course_row.get('course_name')) else ''
                course_code = course_row['course_code'] if pd.notna(course_row.get('course_code')) else ''
                course_header = f"{course_name}[{course_code}]"
            
            if course_header not in course_order:
                continue
            
            # extract course summary values
            total_marks = safe_int_convert(course_row.get('total_marks', 0))
            grade = course_row.get('grade', '') if pd.notna(course_row.get('grade')) else ''
            grade_point = safe_int_convert(course_row.get('grade_point', 0))
            course_credits = safe_int_convert(course_row.get('course_credits', 0))
            earned_credits = safe_int_convert(course_row.get('earned_credit', 0))
            is_failed = course_row.get('is_failed', '') if pd.notna(course_row.get('is_failed')) else ''
            unit_point = safe_int_convert(course_row.get('unit_point', 0))
            
            # find row indices for this student
            if isinstance(pivot.index, pd.MultiIndex):
                if 'registration_id' in pivot.index.names:
                    mask = pivot.index.get_level_values('registration_id') == registrationId
                    row_indices = pivot.index[mask].tolist()
                else:
                    row_indices = []
            else:
                if 'registration_id' in pivot.columns:
                    mask = pivot['registration_id'] == registrationId
                    row_indices = pivot.index[mask].tolist()
                else:
                    row_indices = []
            
            # fill summary columns for this student's course according to index
            if row_indices:
                for idx in row_indices:
                    try:
                        pivot.at[idx, (course_header, 'Total', 'Total')] = total_marks
                        pivot.at[idx, (course_header, 'Grade', 'Grade')] = grade
                        pivot.at[idx, (course_header, 'Grade Point', 'Grade Point')] = grade_point
                        pivot.at[idx, (course_header, 'Course Credits', 'Course Credits')] = course_credits
                        pivot.at[idx, (course_header, 'Earned Credits', 'Earned Credits')] = earned_credits
                        pivot.at[idx, (course_header, 'is_failed', 'is_failed')] = is_failed
                        pivot.at[idx, (course_header, 'Unit Point', 'Unit Point')] = unit_point
                    except Exception:
                        continue
    
    # calculate total_marks from assessment_obtained_marks for each student
    # Group by student_ukid and sum all assessment_obtained_marks
    if 'assessment_obtained_marks' in data.columns:
        total_marks_by_student = data.groupby('student_ukid')['assessment_obtained_marks'].sum().reset_index()
        total_marks_by_student.columns = ['student_ukid', 'total_marks']
    else:
        total_marks_by_student = pd.DataFrame(columns=['student_ukid', 'total_marks'])
    
    # calculate overall student summary stats (total_grade, total_credit, etc.)
    statuslst = []
    totalGrade = []
    totalCredits = []
    earnedCredits = []
    totalUnitPoint = []
    totalMarks = []
    pass_statuslst = []
    
    for registrationId in regId:
        # get student_ukid using same logic as used above
        if isinstance(pivot.index, pd.MultiIndex):
            if 'registration_id' in pivot.index.names:
                student_rows = pivot[pivot.index.get_level_values('registration_id') == registrationId]
                if student_rows.empty:
                    continue
                student_ukid = student_rows.index.get_level_values('student_ukid')[0]
            else:
                student_data = data[data['registration_id'] == registrationId]
                if student_data.empty:
                    continue
                student_ukid = student_data['student_ukid'].iloc[0]
        else:
            if 'registration_id' in pivot.columns:
                student_rows = pivot[pivot['registration_id'] == registrationId]
                if student_rows.empty:
                    continue
                student_ukid = student_rows['student_ukid'].iloc[0] if 'student_ukid' in pivot.columns else None
            else:
                student_data = data[data['registration_id'] == registrationId]
                if student_data.empty:
                    continue
                student_ukid = student_data['student_ukid'].iloc[0]
        
        if student_ukid is None:
            continue
        
        # get summary stats from summary_df
        student_summary = summary_df[summary_df['student_ukid'] == student_ukid]
        
        # get total_marks from assessment marks data
        student_total_marks = total_marks_by_student[total_marks_by_student['student_ukid'] == student_ukid]
        if not student_total_marks.empty:
            total_marks_value = safe_int_convert(student_total_marks.iloc[0]['total_marks'])
        else:
            total_marks_value = 0
        
        if not student_summary.empty:
            summary_row = student_summary.iloc[0]
            totalGrade.append(safe_int_convert(summary_row.get('total_grade', 0)))
            totalCredits.append(safe_int_convert(summary_row.get('total_credits', 0)))
            earnedCredits.append(safe_int_convert(summary_row.get('total_earned_credits', 0)))
            totalUnitPoint.append(safe_int_convert(summary_row.get('total_unit_point', 0)))
            totalMarks.append(total_marks_value)
            statuslst.append(safe_int_convert(summary_row.get('failed_subject_count', 0)))
            
            student_courses = course_grades_df[course_grades_df['student_ukid'] == student_ukid]
            pass_status = ""
            for _, r in student_courses.iterrows():
                if r.get('is_failed') == 'Fail':
                    string = r.get('course_code', '') or ''
                    if string:  # Only add if course_code is not empty
                        pass_status = "(" + string + ")" + pass_status
            pass_statuslst.append(pass_status if pass_status else 'Pass')
        else:
            # give 0  values if no summary found
            totalGrade.append(0)
            totalCredits.append(0)
            earnedCredits.append(0)
            totalUnitPoint.append(0)
            totalMarks.append(total_marks_value)
            statuslst.append(0)
            pass_statuslst.append('Pass')
    
    # add overall summary columns to pivot
    pivot['total_grade'] = totalGrade
    pivot["total_credit"] = totalCredits
    pivot['total_earned_credit'] = earnedCredits
    pivot["total_unit_point"] = totalUnitPoint
    pivot["total_marks"] = totalMarks
    pivot["failed_subject_count"] = statuslst
    pivot["failed_subject_count"] = pivot["failed_subject_count"].replace([''], '0')
    pivot['remarks'] = pass_statuslst
    pivot["remarks"] = pivot["remarks"].replace([''], 'Pass')
    
    return pivot, course_order

def generate_excel_report(pivot_df, tenant_name, programme, year_of_joining, term_name, examination_name, course_order): # generates Excel file with formatted headers and multi-level columns
    final = pivot_df.copy()
    
    # convert index to columns for Excel export
    try:
        if isinstance(final.index, pd.MultiIndex):
            # Reset index first
            final = final.reset_index()
            
            # If there are duplicate column names (from index and existing columns), 
            # keep the data from the existing columns, not the index
            if final.columns.duplicated().any():
                # Find duplicate columns
                seen = {}
                cols_to_drop = []
                for i, col in enumerate(final.columns):
                    if col in seen:
                        # We have a duplicate - keep the first occurrence (which should be the data column)
                        # and drop the one from reset_index (which comes after)
                        cols_to_drop.append(i)
                    else:
                        seen[col] = i
                
                # Drop the duplicate columns (from index)
                if cols_to_drop:
                    final = final.drop(final.columns[cols_to_drop], axis=1)
        else:
            # Simple index reset
            final.reset_index(inplace=True)
    except ValueError as e:
        if 'duplicate' in str(e).lower():
            # Fallback: remove duplicates keeping first occurrence
            final = final.loc[:, ~final.columns.duplicated()]
            if not isinstance(final.index, pd.RangeIndex):
                final.reset_index(inplace=True)
        else:
            raise
    
    # remove duplicate student rows
    if final.duplicated(subset=['student_ukid', 'registration_id', 'student_name', 'sgpa', 'cgpa']).any():
        final = final.drop_duplicates(subset=['student_ukid', 'registration_id', 'student_name', 'sgpa', 'cgpa'], keep='first')
    
    # identify column groups for ordering acc to old report
    student_info_cols = ['student_ukid', 'registration_id', 'student_name']
    student_info_cols_present = [col for col in student_info_cols if col in final.columns]
    
    cgpa_sgpa_cols = []
    if 'sgpa' in final.columns:
        cgpa_sgpa_cols.append('sgpa')
    if 'cgpa' in final.columns:
        cgpa_sgpa_cols.append('cgpa')
    
    summary_cols = ['total_grade', 'total_credit', 'total_earned_credit', 'total_unit_point', 
                   'total_marks', 'failed_subject_count', 'remarks']
    summary_cols_present = [col for col in summary_cols if col in final.columns]
    
    assessment_columns = [col for col in final.columns if col not in summary_cols_present 
                         and col not in student_info_cols_present and col not in cgpa_sgpa_cols]
    
    # build column order first student info, then course info, then summary data
    final_column_order = []
    seen_cols = set()
    
    final_column_order.extend(student_info_cols_present)
    seen_cols.update(student_info_cols_present)
    
    # add course assessment and summary columns in course order
    for course in course_order:
        # Get all assessment columns (marks, moderation, re-evaluation, maximum)
        course_assessments = [col for col in assessment_columns 
                             if isinstance(col, tuple) and col[0] == course 
                             and col[1] not in ['Grade', 'Grade Point', 'Course Credits', 'Earned Credits', 'is_failed', 'Unit Point']
                             and col not in seen_cols]
        final_column_order.extend(course_assessments)
        seen_cols.update(course_assessments)
        
        # Get course-level grade columns (Grade, Grade Point, Course Credits, etc.)
        course_grade_cols = [col for col in final.columns 
                           if isinstance(col, tuple) and col[0] == course 
                           and col[1] == ''  # Empty component level for course-level columns
                           and col[2] in ['Grade', 'Grade Point', 'Course Credits', 'Earned Credits', 'is_failed', 'Unit Point']
                           and col not in seen_cols]
        final_column_order.extend(course_grade_cols)
        seen_cols.update(course_grade_cols)
        
        # Get course summary columns (Total)
        course_summaries = [col for col in final.columns 
                           if isinstance(col, tuple) and col[0] == course and col[1] == 'Total' 
                           and col not in seen_cols]
        final_column_order.extend(course_summaries)
        seen_cols.update(course_summaries)
    
    # add remaining columns (excluding summary columns which will be added at the end)
    remaining = [col for col in final.columns if col not in seen_cols 
                 and col not in cgpa_sgpa_cols and col not in summary_cols_present]
    final_column_order.extend(remaining)
    
    # add CGPA/SGPA and summary columns at the end of report 
    final_column_order.extend(cgpa_sgpa_cols)
    seen_cols.update(cgpa_sgpa_cols)
    
    final_column_order.extend(summary_cols_present)
    seen_cols.update(summary_cols_present)
    
    final_column_order = list(dict.fromkeys(final_column_order))
    
    missing_cols = [col for col in final_column_order if col not in final.columns]
    if missing_cols:
        final_column_order = [col for col in final_column_order if col in final.columns]
    
    try:
        final = final[final_column_order]
    except (KeyError, ValueError) as e:
        if 'duplicate' in str(e).lower():
            final = final.loc[:, ~final.columns.duplicated()]
            final_column_order = [col for col in final_column_order if col in final.columns]
            final = final[final_column_order]
        else:
            raise
    
    # create MultiIndex columns for 3-level header structure for 3 level pivot structrure
    level0_list = []
    level1_list = []
    level2_list = []
    
    for col in final.columns:
        if isinstance(col, tuple):
            level0_list.append(col[0] if len(col) > 0 else '')
            level1_list.append(col[1] if len(col) > 1 else '')
            level2_list.append(col[2] if len(col) > 2 else '')
        else:
            level0_list.append('')
            level1_list.append('')
            level2_list.append(str(col))
    
    final.columns = pd.MultiIndex.from_arrays([level0_list, level1_list, level2_list], 
                                             names=['Course', 'Component', 'Assessment'])
    
    # Output path: tenant_name/exam_name/programme_name - batch_year.xlsx
    output_base_dir = Path(r"C:\Users\suraj\OneDrive\Desktop\TR Report Outputs") 
    tenant_output_dir = output_base_dir / tenant_name
    tenant_output_dir.mkdir(parents=True, exist_ok=True)
    
    exam_name_clean = examination_name.replace('/', '_').replace('\\', '_').replace(':', '_')
    exam_output_dir = tenant_output_dir / exam_name_clean
    exam_output_dir.mkdir(parents=True, exist_ok=True)
    
    programme_clean = str(programme).replace('/', '_').replace('\\', '_').replace(':', '_') if programme else 'Unknown'
    year_clean = str(year_of_joining) if year_of_joining else 'Unknown'
    fileName = exam_output_dir / f"{programme_clean} - {year_clean}.xlsx"
    
    writer = pd.ExcelWriter(str(fileName), engine='xlsxwriter')
    
    if isinstance(final.columns, pd.MultiIndex):
        final.columns.names = ['Course', 'Component', 'Assessment']
    
    # Write to Excel - write data WITHOUT headers (header=False) starting at row 9
    # Headers are already written manually at rows 6-8
    # Ensure index is RangeIndex and starts from 1
    if not isinstance(final.index, pd.RangeIndex):
        final = final.reset_index(drop=True)
    
    # Change index to start from 1 instead of 0
    final.index = pd.RangeIndex(start=1, stop=len(final) + 1)
    
    # Write data with index=True (required for MultiIndex columns)
    # Use header=False to prevent pandas from writing its own headers
    final.to_excel(writer, sheet_name='Sheet1', index=True, startrow=9, header=False, merge_cells=False)
    
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    
    # format for header cells top 4 rows border
    header_format = workbook.add_format({
        'align': 'center',
        'valign': 'vcenter',
        'bold': True,
        'bg_color': '#D3D3D3',
        'border': 1
    })
    
    # Since we're writing with index=True, there's 1 index column
    # The index column will be in column 0
    num_index_cols = 1
    
    # Write index column header manually (since we're using header=False)
    # Leave it empty or write a simple header
    worksheet.write(6, 0, '', header_format)
    worksheet.write(7, 0, '', header_format)
    worksheet.write(8, 0, '', header_format)  # Could write 'S.No.' or leave empty
    
    # write multi-level headers: row 6 = course, row 7 = component, row 8 = assessment -  3 tier
    if isinstance(final.columns, pd.MultiIndex):
        col_idx = num_index_cols
        component_groups = {} # for component middle layer
        course_groups = {} # for course header layer
        
        for col in final.columns:
            course, component, assessment = col
            
            if not course and not component:
                #writing last few columns of summary here
                worksheet.write(6, col_idx, '', header_format)
                worksheet.write(7, col_idx, '', header_format)
                worksheet.write(8, col_idx, str(assessment), header_format)
                col_idx += 1
            else:
                # group by course for merging course headers
                if course and course not in course_groups:
                    course_groups[course] = []
                if course:
                    course_groups[course].append(col_idx)
                
                # group by component for merging component headers
                key = (course, component)
                if key not in component_groups:
                    component_groups[key] = []
                component_groups[key].append(col_idx)
                
                worksheet.write(6, col_idx, '', header_format)
                if component:
                    worksheet.write(7, col_idx, str(component), header_format)
                if assessment:
                    worksheet.write(8, col_idx, str(assessment), header_format)
                
                col_idx += 1
        
        # merge and write course headers in row 6
        for course, col_indices in course_groups.items():
            if len(col_indices) > 0:
                start_col = min(col_indices)
                end_col = max(col_indices)
                worksheet.merge_range(6, start_col, 6, end_col, str(course), header_format)
        
        # merge component headers in row 7
        for (course, component), col_indices in component_groups.items():
            if len(col_indices) > 1:
                start_col = min(col_indices)
                end_col = max(col_indices)
                worksheet.merge_range(7, start_col, 7, end_col, str(component), header_format)
        
        # merge summary component headers to mantain summary header
        # Skip grade columns with empty component (they don't need component-level merging)
        summary_groups = {}
        col_idx = num_index_cols
        for col in final.columns:
            if isinstance(col, tuple) and len(col) == 3:
                course, component, assessment = col
                # Only merge if component is not empty and it's a summary column
                if component and (assessment == component or assessment == 'Total'):
                    key = (course, component)
                    if key not in summary_groups:
                        summary_groups[key] = []
                    summary_groups[key].append(col_idx)
            col_idx += 1
        
        for (course, component), col_indices in summary_groups.items():
            if len(col_indices) > 1:
                start_col = min(col_indices)
                end_col = max(col_indices)
                if end_col - start_col == len(col_indices) - 1:
                    worksheet.merge_range(7, start_col, 7, end_col, str(component), header_format)
    
    # set column widths based on content using old column alphabet method above
    try:
        for column in final:
            if isinstance(column, tuple):
                column_str = ' - '.join([str(c) for c in column])
            else:
                column_str = str(column)
            column_width = max(final[column].astype(str).map(len).max(), len(column_str))
            col_idx = final.columns.get_loc(column)
            actual_col_idx = col_idx + num_index_cols
            worksheet.set_column(actual_col_idx, actual_col_idx, min(column_width + 2, 30))
    except ValueError:
        pass
    
    # write header rows top 4 rows
    headerSize = 16
    num_cols = len(final.columns) + 1
    col_letter = number_to_alphabet(num_cols)
    
    header_format_large = workbook.add_format({
        'align': 'center',
        'bold': True,
        'color': '#000234',
        'size': headerSize
    })
    
    worksheet.merge_range(f'A1:{col_letter}1', tenant_name.upper(), header_format_large)
    worksheet.merge_range(f'A2:{col_letter}2', f'Programme - {programme}', header_format_large)
    worksheet.merge_range(f'A3:{col_letter}3', f'Batch Year - {year_of_joining}', header_format_large)
    worksheet.merge_range(f'A4:{col_letter}4', f'Term - {term_name}', header_format_large)
    worksheet.merge_range(f'A5:{col_letter}5', f'Examination - {examination_name}', header_format_large)
    
    # add borders to data cells - bold border
    border_fmt = workbook.add_format({'bottom': 4, 'top': 4, 'left': 4, 'right': 4})
    worksheet.conditional_format(
        xlsxwriter.utility.xl_range(9, 0, len(final) + 10, num_cols),
        {'type': 'no_errors', 'format': border_fmt}
    )
    
    # set column widths using get_col_widths function to avoid overlap between data
    try:
        for i, width in enumerate(get_col_widths(final)):
            worksheet.set_column(i, i, min(width, 30))
    except ValueError:
        pass
    
    writer.close()
    print(f"  Report saved: {fileName}")
    print(f"  Location: {exam_output_dir}")

def main():
    warnings.filterwarnings('ignore')

    
    tenant_name = input("\nEnter tenant name: ").strip() 
    if not tenant_name:
        print("Error: Tenant name cannot be empty!")
        return
    
    exam_input = input("Enter examination IDs (comma-separated, REQUIRED): ").strip()
    if not exam_input:
        print("Error: Examination IDs are required!")
        return
    # for multiple exam ids
    try:
        exam_ids = [int(x.strip()) for x in exam_input.split(',')]
    except ValueError:
        print("Error: Invalid examination ID format!")
        return
    #
    term_input = input("Enter term IDs (comma-separated, REQUIRED): ").strip()
    if not term_input:
        print("Error: Term IDs are required!")
        return
    # for multiple term ids
    try:
        term_ids = [int(x.strip()) for x in term_input.split(',')]
    except ValueError:
        print("Error: Invalid term ID format!")
        return
    
    conn = connect_to_tenant_database(tenant_name)
    print("connected.")
    try:
        # Initialize empty dataframes to combine results
        course_grades_list = []
        cgpa_sgpa_list = []
        assessment_marks_list = []
        
        # Loop through each exam_id individually
        print(f"\nFetching data for {len(exam_ids)} exam ID(s)...")
        for exam_id in exam_ids:
            print(f"  Processing exam ID: {exam_id}")
            EXAM_ID = str(exam_id)
            
            # Fetch course grades for this exam_id
            course_grades_temp = fetch_course_grades_data(conn, EXAM_ID)
            if not course_grades_temp.empty:
                course_grades_list.append(course_grades_temp)
            
            # Fetch cgpa/sgpa for this exam_id
            cgpa_sgpa_temp = fetch_cgpa_sgpa_data(conn, EXAM_ID)
            if not cgpa_sgpa_temp.empty:
                cgpa_sgpa_list.append(cgpa_sgpa_temp)
        
        # Loop through each term_id individually
        print(f"\nFetching data for {len(term_ids)} term ID(s)...")
        for term_id in term_ids:
            print(f"  Processing term ID: {term_id}")
            TERM_ID = str(term_id)
            
            # Fetch assessment marks for this term_id
            assessment_marks_temp = fetch_assessment_marks_data(conn, TERM_ID)
            if not assessment_marks_temp.empty:
                assessment_marks_list.append(assessment_marks_temp)
        
        # Combine all dataframes
        if course_grades_list:
            course_grades_df = pd.concat(course_grades_list, ignore_index=True)
        else:
            course_grades_df = pd.DataFrame()
        
        if cgpa_sgpa_list:
            cgpa_sgpa_df = pd.concat(cgpa_sgpa_list, ignore_index=True)
        else:
            cgpa_sgpa_df = pd.DataFrame()
        
        if assessment_marks_list:
            assessment_marks_df = pd.concat(assessment_marks_list, ignore_index=True)
        else:
            assessment_marks_df = pd.DataFrame()
        
        # check if course grade fetch is empty
        if course_grades_df.empty:
            print("Error: No course grades data fetched!")
            return
        
        # Group data by examination_name to process each examination separately
        unique_examinations = course_grades_df['examination_name'].dropna().unique().tolist()
        
        if not unique_examinations:
            print("Error: No examination names found in data!")
            return
        
        # Process each examination separately
        for examination_name in unique_examinations:
            print(f"\n{'='*60}")
            print(f"Processing Examination: {examination_name}")
            print(f"{'='*60}")
            
            # Filter data for this examination
            exam_course_grades_df = course_grades_df[course_grades_df['examination_name'] == examination_name].copy()
            
            if exam_course_grades_df.empty:
                print(f"  No course grades data for {examination_name}, skipping")
                continue
            
            # Get exam_id for this examination to filter related data
            exam_ids_for_this_exam = exam_course_grades_df['exam_id'].unique().tolist()
            
            # Filter cgpa_sgpa_df for this examination
            exam_cgpa_sgpa_df = cgpa_sgpa_df[cgpa_sgpa_df['exam_id'].isin(exam_ids_for_this_exam)].copy() if not cgpa_sgpa_df.empty else pd.DataFrame()
            
            # Get term_ids for this examination to filter assessment marks
            term_ids_for_this_exam = exam_course_grades_df['term_id'].unique().tolist()
            
            # Filter assessment_marks_df for terms related to this examination
            exam_assessment_marks_df = assessment_marks_df[assessment_marks_df['term_id'].isin(term_ids_for_this_exam)].copy() if not assessment_marks_df.empty else pd.DataFrame()
            
            # Get student UKIDs for this examination
            exam_student_ukids = exam_course_grades_df['student_ukid'].unique().tolist()
            EXAM_STUDENT_UKIDS = ','.join([f"'{ukid}'" for ukid in exam_student_ukids])
            
            # Fetch user data for students in this examination
            exam_user_df = fetch_user_data(conn, EXAM_STUDENT_UKIDS)
            
            if exam_user_df.empty:
                print(f"  No user data for {examination_name}, skipping")
                continue
            
            # Calculate summary for this examination
            exam_summary_df = fetch_summary_columns(exam_course_grades_df)
            
            # Get term_name for this examination
            term_name = exam_course_grades_df['term_name'].iloc[0] if not exam_course_grades_df['term_name'].isna().all() else 'Unknown'
            
            # Merge data for this examination
            merged_data = merging_dataframes_for_pivot(exam_user_df, exam_course_grades_df, exam_assessment_marks_df, exam_cgpa_sgpa_df, exam_summary_df)
            prepared_data = prepare_pivot_data(merged_data)
            
            if prepared_data.empty:
                print(f"  No prepared data for {examination_name}, skipping")
                continue
            
            # Generate separate report for each programme and batch year combination for this examination
            for (programme, year_of_joining) in prepared_data[['programme_name', 'year_of_joining']].drop_duplicates().values.tolist():
                print(f"\nGenerating report for: {programme} - {year_of_joining}")
                
                temp = prepared_data[(prepared_data['programme_name'] == programme) & 
                                    (prepared_data['year_of_joining'] == year_of_joining)]
                
                if temp.empty:
                    print(f"  No data for {programme} - {year_of_joining}, skipping file generation")
                    continue
                
                pivot_obtained, pivot_moderation, pivot_reevaluation, pivot_maximum, data_dedup = create_pivot_tables(temp)
                
                # Check if pivot tables have any data
                if pivot_obtained.empty or len(pivot_obtained.index) == 0:
                    print(f"  No pivot data for {programme} - {year_of_joining}, skipping file generation")
                    continue
                
                course_order = []
                if 'course_header' in temp.columns:
                    for course in temp['course_header'].unique():
                        if course in pivot_obtained.columns.get_level_values(0):
                            course_order.append(course)
                
                # Check if there are any courses
                if not course_order:
                    print(f"  No courses found for {programme} - {year_of_joining}, skipping file generation")
                    continue
                
                pivot = build_combined_pivot(pivot_obtained, pivot_moderation, pivot_reevaluation, 
                                           pivot_maximum, course_order, exam_course_grades_df)
                
                # Check if pivot has data after building
                if pivot.empty or len(pivot.index) == 0:
                    print(f"  No data in pivot for {programme} - {year_of_joining}, skipping file generation")
                    continue
                
                pivot_with_summary, course_order_final = add_summary_columns(
                    pivot, temp, exam_course_grades_df, exam_summary_df
                )
                
                # Final check before generating report
                if pivot_with_summary.empty or len(pivot_with_summary.index) == 0:
                    print(f"  No data in final pivot for {programme} - {year_of_joining}, skipping file generation")
                    continue
                
                generate_excel_report(pivot_with_summary, tenant_name, programme, year_of_joining, 
                                    term_name, examination_name, course_order_final)
        
        print("\nsuccessful")
        
    finally:
        conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    main()



