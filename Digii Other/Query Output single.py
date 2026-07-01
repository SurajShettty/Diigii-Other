import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error


def fetch_data(query):
    mydb = mysql.connector.connect(
        host="collpolldb11-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        user="suraj_shetty",
        passwd="pTXr8yJmOR",
        database="collpoll_gdgu"
    )

    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute(query)
    raw_data = mycursor.fetchall()
    return pd.DataFrame(raw_data)
    
query = f'''
            SELECT 
                ccs.name AS ccs_name, 
                p.programme_name, 
                dd.department_name as programme_dept, 
                c.batch_year, 
                cc.sequence, 
                crt.name AS enrolment_type, 
                if(
                    cc.is_term_dependent = 1, 'Term Specific', 
                    'Term Independent'
                ) curriculum_type, 
                s.name specialisation, 
                psm.specialisation_type, 
                ccc.course_code, cv.id as course_version_id,cv.version,
                cv.course_name, 
                cct.name as component_type, 
                cco.course_credits as component_credits, 
                d.department_name as course_offered_by_dept, 
                ccc.course_credits, 
                ccs.min_courses, 
                ccs.max_courses, 
                ccs.min_credits, 
                ccs.max_credits 
            FROM curriculum c 
            LEFT JOIN curriculum_cluster cc ON cc.curriculum_id = c.id 
            LEFT JOIN curriculum_cluster_set ccs ON ccs.curriculum_cluster_id = cc.id 
            LEFT JOIN course_registration_type crt ON crt.id = ccs.course_registration_type_id 
            LEFT JOIN programme p ON p.programme_id = c.programme_id 
            LEFT JOIN department dd on dd.department_id = p.department_id 
            LEFT JOIN curriculum_course ccc ON ccc.curriculum_cluster_set_id = ccs.id 
            LEFT JOIN course_version cv on cv.id = ccc.course_version_id 
            LEFT JOIN course cccc on cv.course_id = cccc.course_id 
            LEFT JOIN department d on d.department_id = cccc.department_id 
            LEFT JOIN programme_specialisation_mapping psm on psm.id = c.programme_specialisation_mapping_id 
            LEFT JOIN specialisation s on psm.specialisation_id = s.id 
            LEFT JOIN course_component cco on cco.course_version_id = cv.id 
                left join course_component_type cct on cct.id = cco.course_component_type_id
            WHERE 
                 sequence IS NOT NULL 
                AND ccc.course_code IS NOT NULL 
                AND ccs.is_deleted = 0 
                '''


# fetching data from query to df
df = fetch_data(query)
# df['duration'] = (
#     df['duration']
#     .astype(str)
#     .str.extract(r'(\d{2}:\d{2}:\d{2})', expand=False)
# )


# Create an empty list to store error messages
error_logs = []


# Save error logs to Excel
df.to_excel(f'C:/Users/suraj/OneDrive/Desktop/IILMGG Seating Plan {(pd.Timestamp.now()).strftime("%Y-%m-%d %H-%M")}.xlsx', index=False)