import pandas as pd

# ---------------------------
# 1. Load Data
# ---------------------------
feedback = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\MAB sess 1 6 254 feedback raw.csv")
class_students = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\mab session 6 feedback class_student.csv")

# Normalize column names
feedback.columns = [c.strip().lower() for c in feedback.columns]
class_students.columns = [c.strip().lower() for c in class_students.columns]

# ---------------------------
# 2. Consolidated Respondents
# ---------------------------
consolidated = feedback.groupby([
    'session_name', 'term', 'programme_name', 'course_code', 'course_name',
    'type', 'class_id', 'batch', 'faculty_name', 'faculty_ukid', 'template_name',
    'student_ukid', 'session_id', 'template_id'
]).agg(
    submitted=('submitted', 'max'),
    avg_score=('option_score', 'mean'),
    response_status=('response_status', 'first'),
    report_published=('report_published', 'first')
).reset_index()
consolidated['avg_score'] = consolidated['avg_score'].round(2)

# ---------------------------
# 3. Class Metadata per (class, session, course, faculty, template)
# ---------------------------
class_metadata = feedback.groupby(
    ['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id']
).first().reset_index()

metadata_cols = [
    'class_id', 'session_name', 'term', 'programme_name', 'course_code',
    'course_name', 'type', 'batch', 'faculty_name', 'faculty_ukid',
    'template_name', 'session_id', 'template_id', 'report_published'
]
class_metadata = class_metadata[metadata_cols]

# ---------------------------
# 4. Find Non-Respondents per (session, course, faculty)
# ---------------------------
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

# ---------------------------
# 5. Calculate number of questions per combination
# ---------------------------
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

# ---------------------------
# 6. Consolidate full dataset
# ---------------------------
consolidated_full = pd.concat([consolidated, non_respondents], ignore_index=True)

# ---------------------------
# 7. Faculty Summary (Using full dataset)
# ---------------------------
faculty_summary = (
    consolidated_full.groupby(['faculty_name', 'term'])
    .agg(
        courses=('course_code', 'nunique'),
        class_groups=('class_id', 'nunique'),
        avg_score=('avg_score', lambda x: round(pd.Series(x).dropna().mean(), 2)),
        participation_pct=('submitted', lambda x: round(x.sum() / len(x) * 100, 2)),
        std_dev_score=('avg_score', lambda x: round(pd.Series(x).dropna().std(), 2))
    )
    .reset_index()
)
# High Satisfaction Rate
# Step 1: Calculate max option score per combination
max_scores = (
    feedback.groupby(['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'])['option_score']
    .max()
    .reset_index(name='max_option_score')
)

# Step 2: Merge max scores back to feedback
feedback = feedback.merge(
    max_scores,
    on=['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'],
    how='left'
)

# Step 3: Calculate normalized score per row
feedback['normalized_score'] = feedback['option_score'] / feedback['max_option_score']

# Step 4: Calculate high satisfaction % using normalized score >= 0.8 (or your chosen threshold)
high_sat = (
    feedback.groupby(['faculty_name', 'term'])
    .apply(lambda df: round((df['normalized_score'] >= 0.8).sum() / len(df) * 100, 2))
    .reset_index(name='high_sat_%')
)

faculty_summary = faculty_summary.merge(high_sat, on=['faculty_name', 'term'], how='left')

# ---------------------------
# 8. Course Summary (Using full dataset)
# ---------------------------
course_summary = (
    consolidated_full.groupby(['course_code', 'term'])
    .agg(
        faculty_count=('faculty_name', 'nunique'),
        components=('type', 'nunique'),
        avg_score=('avg_score', lambda x: round(pd.Series(x).dropna().mean(), 2)),
        std_dev_score=('avg_score', lambda x: round(pd.Series(x).dropna().std(), 2)),
        participation_pct=('submitted', lambda x: round(x.sum() / len(x) * 100, 2))
    )
    .reset_index()
)

# ---------------------------
# 9. Programme Summary (Using full dataset)
# ---------------------------
programme_summary = (
    consolidated_full.groupby(['programme_name', 'term'])
    .agg(
        courses=('course_code', 'nunique'),
        avg_score=('avg_score', lambda x: round(pd.Series(x).dropna().mean(), 2)),
        coverage_pct=('submitted', lambda x: round(x.sum() / len(x) * 100, 2)),
        std_dev_score=('avg_score', lambda x: round(pd.Series(x).dropna().std(), 2))
    )
    .reset_index()
)

# ---------------------------
# 10. Export all summaries to Excel
# ---------------------------
output_path = r"C:\Users\Suraj Shetty\OneDrive\Desktop\feedback_summary_with_full_nonrespondents.xlsx"
with pd.ExcelWriter(output_path) as writer:
    consolidated_full.to_excel(writer, sheet_name="Consolidated Report", index=False)
    faculty_summary.to_excel(writer, sheet_name="Faculty Summary", index=False)
    course_summary.to_excel(writer, sheet_name="Course Summary", index=False)
    programme_summary.to_excel(writer, sheet_name="Programme Summary", index=False)

print(f"✅ Excel file generated: {output_path}")
