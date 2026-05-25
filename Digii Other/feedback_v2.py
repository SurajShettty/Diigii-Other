import pandas as pd

# 1. Load Data
feedback = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\MAB sess 1 6 254 579 feedback raw.csv")
class_students = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\mab session 6 feedback class_student.csv")

# Normalize column names
feedback.columns = [c.strip().lower() for c in feedback.columns]
class_students.columns = [c.strip().lower() for c in class_students.columns]

# 2. Consolidated Respondents
consolidated = feedback.groupby([
	'session_name', 'term', 'programme_name', 'course_department', 'programme_section_name',
	'course_code', 'course_name', 'type', 'class_id', 'batch',
	'faculty_name', 'faculty_ukid', 'template_name',
	'student_ukid', 'session_id', 'template_id'
]).agg(
	submitted=('submitted', 'max'),
	avg_score=('option_score', 'mean'),
	response_status=('response_status', 'first'),
	report_published=('report_published', 'first')
).reset_index()
consolidated['avg_score'] = consolidated['avg_score'].round(2)

# 3. Class Metadata per (class, session, course, faculty, template)
class_metadata = feedback.groupby(
    ['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id']
).first().reset_index()

metadata_cols = [
    'class_id', 'session_name', 'term', 'programme_name', 'course_department', 'programme_section_name','course_code',
    'course_name', 'type', 'batch', 'faculty_name', 'faculty_ukid',
    'template_name', 'session_id', 'template_id', 'report_published'
]
class_metadata = class_metadata[metadata_cols]

# 4. Find Non-Respondents per (session, course, faculty)
# Unique teaching instances
teaching_instances = feedback[[
    'class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
]].drop_duplicates()

# Combine with students in each class
expected_responses = teaching_instances.merge(class_students, on='class_id', how='left')

# Merge with actual responses to identify who didn't submit
merged = expected_responses.merge(
    consolidated[[
        'class_id', 'student_ukid', 'session_id', 'course_code',
        'faculty_ukid', 'template_id', 'submitted'
    ]],
    on=['class_id', 'student_ukid', 'session_id', 'course_code', 'faculty_ukid', 'template_id'],
    how='left'
)

# Non-respondents have NaN submitted
non_respondents = merged[merged['submitted'].isna()].copy()

# Add metadata
non_respondents = non_respondents.merge(
    class_metadata,
    on=['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'],
    how='left'
)

# Fill non-respondent fields
non_respondents['submitted'] = 0
non_respondents['avg_score'] = None
non_respondents['response_status'] = "Not Responded"

# Match columns with consolidated
non_respondents = non_respondents[consolidated.columns]

# 5. Calculate number of questions per combination
question_counts = (
    feedback.groupby(['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'])['question_id']
    .nunique()
    .reset_index(name='num_questions')
)

# Merge question count into consolidated respondents
consolidated = consolidated.merge(
    question_counts,
    on=['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'],
    how='left'
)

# Merge question count into non-respondents
non_respondents = non_respondents.merge(
    question_counts,
    on=['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'],
    how='left'
)

# 6. Consolidate full dataset
_frames = [consolidated, non_respondents]
_frames = [df for df in _frames if not df.empty]
if _frames:
    consolidated_full = pd.concat(_frames, ignore_index=True)
else:
    consolidated_full = consolidated.head(0).copy()

# 7. Question-Level Summary (Required Columns Only)

# Count responses & avg score per question-option
question_option_counts = (
    feedback.groupby([
        'session_name', 'term','course_department', 'programme_section_name', 'course_code', 'class_id', 'batch','type','faculty_name', 'template_name',
        'question_id', 'question_text', 'option_text'
    ])
    .agg(
        response_count=('student_ukid', 'nunique'),       # unique students responded
        avg_score_option=('option_score', 'mean')         # avg score for this specific option
    )
    .reset_index()
)

# Average score per question (regardless of option)
avg_score_question_level = (
    feedback.groupby([
        'session_name', 'term', 'course_department', 'programme_section_name','course_code', 'class_id', 'batch','type','faculty_name', 'template_name',
        'question_id'
    ])['option_score']
    .mean()
    .reset_index(name='avg_score_question')
)

# Step 3: Max option score per (class, session, course, faculty, template)
max_scores = (
    feedback.groupby(['session_name', 'term','course_department', 'programme_section_name', 'course_code', 'class_id','batch','type', 'faculty_name', 'template_name'])['option_score']
    .max()
    .reset_index(name='max_option_score')
)

# High Satisfaction at question level
# First, merge max scores into feedback to calculate normalized score
feedback_with_max = feedback.merge(
    max_scores,
    on=['session_name', 'term', 'course_department', 'programme_section_name','course_code', 'class_id','batch','type' ,'faculty_name', 'template_name'],
    how='left'
)

# Normalized score
feedback_with_max['normalized_score'] = feedback_with_max['option_score'] / feedback_with_max['max_option_score']

# High satisfaction % at question level
high_sat_question_level = (
    feedback_with_max
    .assign(high_sat=(feedback_with_max['normalized_score'] >= 0.8).astype(int))
    .groupby([
        'session_name', 'term', 'course_department', 'programme_section_name','course_code', 'class_id', 'batch','type','faculty_name', 'template_name',
        'question_id'
    ])['high_sat']
    .mean()
    .mul(100)
    .round(2)
    .reset_index(name='high_sat_%')
)

# Participation metrics per template
def _compute_participation(df: pd.DataFrame, group_cols: list) -> pd.DataFrame:
    grouped = df.groupby(group_cols)['submitted']
    out = grouped.agg(participants_template='sum', expected_template='count').reset_index()
    return out

# Template-level participation
_template_keys = ['session_name', 'term', 'course_department', 'programme_section_name','course_code', 'class_id', 'batch','type','faculty_name', 'template_name']
participation_template = _compute_participation(consolidated_full, _template_keys)

# Merge all required data
question_level_report = question_option_counts.merge(
    avg_score_question_level,
    on=['session_name', 'term', 'course_department', 'programme_section_name','course_code', 'class_id','batch','type', 'faculty_name', 'template_name', 'question_id'],
    how='left'
).merge(
    max_scores,
    on=['session_name', 'term','course_department', 'programme_section_name', 'course_code', 'class_id','batch','type', 'faculty_name', 'template_name'],
    how='left'
).merge(
    high_sat_question_level,
    on=['session_name', 'term', 'course_department', 'programme_section_name','course_code', 'class_id', 'batch','type','faculty_name', 'template_name', 'question_id'],
    how='left'
).merge(
    participation_template,
    on=_template_keys,
    how='left'
)

# Calculate normalized question score
question_level_report['avg_score_question_normalized'] = (
    (question_level_report['avg_score_question'] / question_level_report['max_option_score']) * 10
).round(2)

# Round averages
question_level_report['avg_score_option'] = question_level_report['avg_score_option'].round(2)
question_level_report['avg_score_question'] = question_level_report['avg_score_question'].round(2)

# Keep only required columns
required_columns = [
    'session_name', 'term', 'course_department', 'programme_section_name','course_code', 'class_id','batch','type', 'faculty_name', 'template_name',
    'question_id', 'question_text', 'option_text', 'response_count', 'avg_score_option',
    'avg_score_question', 'avg_score_question_normalized', 'max_option_score', 'high_sat_%',
    'participants_template', 'expected_template'
]

question_level_report = question_level_report[required_columns]

# Optional: Sort for readability
question_level_report = question_level_report.sort_values(
    by=['session_name', 'term','course_department', 'programme_section_name', 'course_code', 'class_id', 'question_id', 'option_text']
)

# 8. Export Updated Excel
output_path = r"C:\Users\Suraj Shetty\OneDrive\Desktop\feedback_summary_v4.xlsx"
with pd.ExcelWriter(output_path) as writer:
    consolidated_full.to_excel(writer, sheet_name="Consolidated Report", index=False)
    question_level_report.to_excel(writer, sheet_name="Question Level Report", index=False)

print(f"✅ Excel file generated: {output_path}")
