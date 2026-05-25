import pandas as pd

# Load datasets
df1 = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\1.csv")  #  select d.department_name,p.programme_name,t1.programme_id,t1.batch_year,t1.type,t1.code,t2.direct_outcome_weightage,t2.indirect_outcome_weightage,t1.attainment_percentage,t1.indirect_attainment_percentage,round(((t1.attainment_percentage*t2.direct_outcome_weightage)+(t1.indirect_attainment_percentage*t2.indirect_outcome_weightage))/100,2) as 'overall_%' from obe_programme t1 left join obe_programme_batch_attainment_distribution t2 on t2.programme_id = t1.programme_id and t2.batch_year = t1.batch_year left join programme p on p.programme_id = t1.programme_id left join department d on d.department_id = p.department_id where t1.is_deleted = 0;
df2 = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\2.csv")   #  select t1.programme_id,t1.batch_year,t1.level_name,t1.from,t1.to from obe_programme_attainment_level t1; 

def get_level(row):
    pid = row['programme_id']
    batch = row['batch_year']
    val = row['overall_%']

    match = df2[
        (df2['programme_id'] == pid) &
        (df2['batch_year'] == batch) &
        (val >= df2['from']) &
        (val <= df2['to'])
    ]

    if not match.empty:
        return match.iloc[0]['level_name']
    return None


df1['level'] = df1.apply(get_level, axis=1)

df1.to_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\output.csv", index=False)

print("Level column added successfully.")