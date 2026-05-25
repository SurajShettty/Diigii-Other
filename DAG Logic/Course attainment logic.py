import pandas as pd

# Load datasets
df1 = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\1.csv")   # SELECT t3.term_course_id,t.name as term,cc.course_code,cv.course_name,student_ukid, t3.code, t3.target, t3.attainment_percentage, t2.max_marks, t2.achieved_marks, ROUND((t2.achieved_marks / t2.max_marks) * 100, 2) 'achieved_%', t2.achieved FROM obe_course_outcomes t3 inner join obe_dashboard_student t1 on t1.term_course_id = t3.term_course_id left join obe_dashboard_student_co_marks t2 ON t3.id = t2.co_id and t1.id = t2.obe_student_id LEFT JOIN term_course tc ON tc.id = t1.term_course_id left join term t on t.id = tc.term_id LEFT JOIN course_version cv ON cv.id = tc.course_version_id LEFT JOIN course cc ON cc.course_id = cv.course_id WHERE t3.is_deleted = 0;
df2 = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\2.csv")   # select term_course_id,level_name,t1.from,t1.to from obe_course_attainment_level t1;

# Function to determine level
def get_level(row):
    term_id = row['term_course_id']
    att = row['attainment_percentage']
    
    match = df2[
        (df2['term_course_id'] == term_id) &
        (att >= df2['from']) &
        (att <= df2['to'])
    ]
    
    if not match.empty:
        return match.iloc[0]['level_name']
    return None

# Apply level mapping
df1['level'] = df1.apply(get_level, axis=1)

# Save result
df1.to_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\output.csv", index=False)