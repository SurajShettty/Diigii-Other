import pandas as pd

# ========== 1. Load Data ==========
feedback = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\MAB sess 1 6 254 579 feedback raw.csv") #feedback query
class_students = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\mab session 6 feedback class_student.csv") # select class_id,ukid from class_student;

# Normalize column names
feedback.columns = feedback.columns.str.strip().str.lower()
class_students.columns = class_students.columns.str.strip().str.lower()

# Common keys
meta_keys = ['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id']
report_keys = [
    'session_name','term','course_department','programme_section_name','course_code',
    'class_id','batch','type','faculty_name','template_name'
]

# ========== 2. Consolidated Respondents ==========
consolidated = (
    feedback.groupby([
        'session_name','term','programme_name','course_department','programme_section_name',
        'course_code','course_name','type','class_id','batch',
        'faculty_name','faculty_ukid','template_name',
        'student_ukid','session_id','template_id'
    ])
    .agg(submitted=('submitted','max'),
         avg_score=('option_score','mean'),
         response_status=('response_status','first'),
         report_published=('report_published','first'))
    .reset_index()
)
consolidated['avg_score'] = consolidated['avg_score'].round(2)

# ========== 3. Class Metadata ==========
class_metadata = (
    feedback.groupby(meta_keys).first().reset_index()[[
        'class_id','session_name','term','programme_name','course_department',
        'programme_section_name','course_code','course_name','type','batch',
        'faculty_name','faculty_ukid','template_name','session_id','template_id','report_published'
    ]]
)

# ========== 4. Non-Respondents ==========
expected_responses = feedback[meta_keys].drop_duplicates().merge(class_students, on='class_id', how='left')

merged = expected_responses.merge(
    consolidated[meta_keys+['student_ukid','submitted']], 
    on=meta_keys+['student_ukid'], how='left'
)

non_respondents = (
    merged[merged['submitted'].isna()]
    .merge(class_metadata, on=meta_keys, how='left')
    .assign(submitted=0, avg_score=None, response_status="Not Responded")
)[consolidated.columns]

# ========== 5. Add Question Counts ==========
question_counts = feedback.groupby(meta_keys)['question_id'].nunique().reset_index(name='num_questions')

for df_name in ['consolidated','non_respondents']:
    vars()[df_name] = vars()[df_name].merge(question_counts, on=meta_keys, how='left')

# ========== 6. Combine Respondents + Non-Respondents ==========
consolidated_full = pd.concat([consolidated, non_respondents], ignore_index=True)

# ========== 7. Question-Level Summary ==========
# ✅ Use only submitted rows for question-level calculations
feedback_submitted = feedback[feedback['response_status'].str.lower() == 'submitted']

question_option_counts = (
    feedback_submitted.groupby(report_keys+['question_id','question_text','option_text'])
    .agg(response_count=('student_ukid','nunique'),
         avg_score_option=('option_score','mean'))
    .reset_index()
)

avg_score_question = (
    feedback_submitted.groupby(report_keys+['question_id'])['option_score']
    .agg(avg_score_question='mean', std_score_question='std')   # ✅ NEW
    .reset_index()
)

max_scores = feedback_submitted.groupby(report_keys)['option_score'].max().reset_index(name='max_option_score')

feedback_norm = feedback_submitted.merge(max_scores, on=report_keys)
feedback_norm['normalized_score'] = feedback_norm['option_score'] / feedback_norm['max_option_score']

high_sat = (
    feedback_norm.assign(high_sat=(feedback_norm['normalized_score']>=0.8).astype(int))
    .groupby(report_keys+['question_id'])['high_sat']
    .mean().mul(100).round(2).reset_index(name='high_sat_%')
)

# Participation (template-level, only submitted count)
# expected = all students (regardless of status)
expected_template = (
    consolidated_full
    .groupby(report_keys)['submitted']
    .agg(expected_template='count')
    .reset_index()
)

# participants = only submitted
participants_template = (
    consolidated_full[consolidated_full['response_status'].str.lower() == 'submitted']
    .groupby(report_keys)['submitted']
    .agg(participants_template='sum')
    .reset_index()
)

# merge both
participation = expected_template.merge(participants_template, on=report_keys, how='left').fillna(0)

# Merge all together
question_level_report = (
    question_option_counts
    .merge(avg_score_question, on=report_keys+['question_id'])
    .merge(max_scores, on=report_keys)
    .merge(high_sat, on=report_keys+['question_id'])
    .merge(participation, on=report_keys, how='left')
)

question_level_report['avg_score_question_normalized'] = (
    (question_level_report['avg_score_question'] / question_level_report['max_option_score']) * 10
).round(2)

# Final selection & rounding
question_level_report = (
    question_level_report.assign(
        avg_score_option=lambda d: d['avg_score_option'].round(2),

        avg_score_question=lambda d: d['avg_score_question'].round(2),
        std_score_question=lambda d: d['std_score_question'].round(2)  #new
    )
    .sort_values(report_keys+['question_id','option_text'])
)

# ========== 8. Export ==========
output_path = r"C:\Users\Suraj Shetty\OneDrive\Desktop\feedback_summary_v4_simplifieddd.xlsx"
with pd.ExcelWriter(output_path) as writer:
    consolidated_full.to_excel(writer, sheet_name="Consolidated Report", index=False)
    question_level_report.to_excel(writer, sheet_name="Question Level Report", index=False)

print(f"✅ Excel file generated: {output_path}")
