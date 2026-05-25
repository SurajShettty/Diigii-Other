import pandas as pd
import re
import html
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font

# =========================
# INPUT FILE
# =========================
input_file = r"C:\Users\suraj\OneDrive\Desktop\JAIN Exams.csv"  # Change file name if needed
output_file = r"C:\Users\suraj\OneDrive\Desktop\JAIN Exams_Summarized_Report.xlsx"

# =========================
# READ INPUT DATA
# =========================
df = pd.read_csv(input_file)

# =========================
# CLEAN COLUMN NAMES
# =========================
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(' ', '_')
)

# =========================
# REMOVE HTML TAGS FROM QUESTION COLUMN
# =========================
if 'question' in df.columns:
    df['question'] = (
        df['question']
        .astype(str)
        .apply(html.unescape)
        .apply(lambda x: re.sub(r'<[^>]+>', '', x))
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
    )

# =========================
# CALCULATIONS USING RAW DATA
# =========================

# Convert numeric columns
if 'maximum_marks' in df.columns:
    df['maximum_marks'] = pd.to_numeric(df['maximum_marks'], errors='coerce').fillna(0)

if 'marks' in df.columns:
    df['marks'] = pd.to_numeric(df['marks'], errors='coerce').fillna(0)

# =========================
# SECTION LEVEL SUMMARY
# =========================
# =========================
# STUDENT-COURSE LEVEL TOTALS
# =========================
course_totals = (
    df.groupby([
        'student_name',
        'registration_id',
        'email_id',
        'course_code'
    ], dropna=False)
    .agg(
        course_max_marks=('maximum_marks', 'sum'),
        course_total_marks=('marks', 'sum')
    )
    .reset_index()
)

# =========================
# SECTION LEVEL SUMMARY
# =========================
summary_df = (
    df.groupby([
        'student_name',
        'registration_id',
        'email_id',
        'course_code',
        'section_name',
        'student_assessment_start_time',
        'student_assessment_end_time',
        'status',
        'final_score'
    ], dropna=False)
    .agg(
        **{
            'Section Level max marks': ('maximum_marks', 'sum'),
            'Section Level marks Obtained': ('marks', 'sum'),
            'Section Level max marks': ('maximum_marks', 'sum'),
            'Section Level marks Obtained': ('marks', 'sum')
        }
    )
    .reset_index()
)

# Merge course level totals
summary_df = summary_df.merge(
    course_totals,
    on=[
        'student_name',
        'registration_id',
        'email_id',
        'course_code'
    ],
    how='left'
)

# Student-course level totals
summary_df['Max. Marks'] = summary_df['course_max_marks']
summary_df['Total Marks Obt.'] = summary_df['course_total_marks']

# Percentage calculation
# summary_df['% Scored'] = (
#     (
#         summary_df['Section Level marks Obtained']
#         / summary_df['Section Level max marks']
#     ) * 100
# ).round(2)

summary_df['% Scored'] = (
    (summary_df['Total Marks Obt.'] / summary_df['Max. Marks']) * 100
).round(2)
# Rename columns
summary_df = summary_df.rename(columns={
    'student_name': 'Student Name',
    'registration_id': 'Registration Id',
    'email_id': 'Email Id',
    'course_code': 'Course Name',
    'section_name': 'Question Section',
    'student_assessment_start_time': 'Start Time',
    'student_assessment_end_time': 'End Time',
    'status': 'Status (Completed / Not Attempted)',
    'final_score': 'Confidence Score'
})

# Final column order
# Remove helper columns
summary_df = summary_df.drop(columns=['course_max_marks', 'course_total_marks'], errors='ignore')

summary_df = summary_df[[
    'Student Name',
    'Registration Id',
    'Email Id',
    'Course Name',
    'Max. Marks',
    'Total Marks Obt.',
    'Question Section',
    'Section Level max marks',
    'Section Level marks Obtained',
    '% Scored',
    'Start Time',
    'End Time',
    'Status (Completed / Not Attempted)',
    'Confidence Score'
]]

# =========================
# CREATE EXCEL WORKBOOK
# =========================
wb = Workbook()

# =========================
# SUMMARY SHEET
# =========================
ws_summary = wb.active
ws_summary.title = 'Summary_Report'

for row in dataframe_to_rows(summary_df, index=False, header=True):
    ws_summary.append(row)

# Bold headers
for cell in ws_summary[1]:
    cell.font = Font(bold=True)

# =========================
# MAKE RAW DATA COLUMN NAMES PROPER
# =========================
raw_df = df.copy()
raw_df.columns = [
    col.replace('_', ' ').title()
    for col in raw_df.columns
]

# =========================
# RAW DATA SHEET
# =========================
ws_raw = wb.create_sheet(title='Raw_Data')

for row in dataframe_to_rows(raw_df, index=False, header=True):
    ws_raw.append(row)

# Bold headers
for cell in ws_raw[1]:
    cell.font = Font(bold=True)

# =========================
# AUTO ADJUST COLUMN WIDTHS
# =========================
for ws in [ws_summary, ws_raw]:
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter

        for cell in column:
            try:
                max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

# =========================
# SAVE FILE
# =========================
wb.save(output_file)

print(f'Report generated successfully: {output_file}')



# SELECT concat(ua.f_name," ",ua.l_name) as student_name,ua.registration_id,a.email email_id, c.course_code, qq.maximum_marks, qqr.marks, qs.title AS section_name, qq.sequence_label AS question_number, qq.question, qq.question_type, t1.student_assessment_start_time, t1.student_assessment_end_time, pus.final_score, t1.answer_sheet_number, t1.question_paper_id, if(student_assessment_start_time is not null,'Completed','Not Attempted') as status FROM ems_assessment_answer_sheet t1 LEFT JOIN ems_assessment_question_paper ttt ON ttt.id = t1.question_paper_id LEFT JOIN ems_assessment ea ON ea.id = ttt.assessment_id LEFT JOIN ems_assessment_schedule eas ON ea.assessment_schedule_id = eas.id LEFT JOIN ems_assessment_question_paper_set tt ON tt.question_paper_id = t1.question_paper_id LEFT JOIN questionnaire q ON q.id = tt.questionnaire_id LEFT JOIN questionnaire_response qr ON q.id = qr.questionnaire_id AND qr.student_ukid = t1.examinee_ukid LEFT JOIN questionnaire_question qq ON qq.questionnaire_id = q.id AND qq.deleted_at IS NULL LEFT JOIN questionnaire_question_response qqr ON qqr.question_id = qq.id AND qqr.questionnaire_response_id = qr.id AND qqr.is_deleted = 0 LEFT JOIN questionnaire_question qq2 ON qq.parent_question_id = qq2.id LEFT JOIN questionnaire_section qs ON qq.section_id = qs.id LEFT JOIN proctor_user_session pus ON pus.entity_id = ea.id AND pus.ukid = t1.examinee_ukid LEFT JOIN term_course tc ON tc.id = ea.term_course_id LEFT JOIN course_version cv ON cv.id = tc.course_version_id LEFT JOIN course c ON c.course_id = cv.course_id left join user_attributes ua on ua.ukid = coalesce(t1.examinee_ukid,qr.student_ukid) left join authenticator a on a.ukid = ua.ukid WHERE eas.id = 60 AND c.course_code IN('GFST2', 'GFST1');

# SELECT cs.ukid AS student_ukid,cs.class_id,concat(ua.f_name," ",ua.l_name) as student_name,ua.registration_id,a.email email_id, c.course_id, crs.course_code, qq.maximum_marks, qqr.marks, qs.title AS section_name, qq.sequence_label AS question_number, qq.question, qq.question_type, ans.student_assessment_start_time, ans.student_assessment_end_time, pus.final_score, ans.answer_sheet_number, ans.question_paper_id, IF(student_assessment_start_time IS NOT NULL, 'Completed', 'Not Attempted') AS status FROM class_student cs left join user_attributes ua on ua.ukid = cs.ukid left join authenticator a on a.ukid = ua.ukid INNER JOIN class c ON c.id = cs.class_id LEFT JOIN term_course tc ON tc.course_id = c.course_id LEFT JOIN course_version cv ON cv.id = tc.course_version_id LEFT JOIN course crs ON crs.course_id = cv.course_id LEFT JOIN ems_assessment ea ON ea.term_course_id = tc.id LEFT JOIN ems_assessment_schedule eas ON eas.id = ea.assessment_schedule_id LEFT JOIN ems_assessment_question_paper qp ON qp.assessment_id = ea.id LEFT JOIN ems_assessment_question_paper_set qps ON qps.question_paper_id = qp.id LEFT JOIN questionnaire q ON q.id = qps.questionnaire_id LEFT JOIN ems_assessment_answer_sheet ans ON ans.question_paper_id = qp.id AND ans.examinee_ukid = cs.ukid LEFT JOIN questionnaire_response qr ON qr.questionnaire_id = q.id AND qr.student_ukid = cs.ukid LEFT JOIN questionnaire_question qq ON qq.questionnaire_id = q.id AND qq.deleted_at IS NULL LEFT JOIN questionnaire_question_response qqr ON qqr.questionnaire_response_id = qr.id AND qqr.question_id = qq.id AND qqr.is_deleted = 0 LEFT JOIN questionnaire_section qs ON qs.id = qq.section_id LEFT JOIN proctor_user_session pus ON pus.entity_id = ea.id AND pus.ukid = cs.ukid WHERE cs.class_id IN(77, 1392) AND eas.id = 60;