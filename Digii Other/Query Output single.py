import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error


def fetch_data(query):
    mydb = mysql.connector.connect(
        host="collpolldb9-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        user="suraj_shetty",
        passwd="3qIGaWCdlh",
        database="collpoll_iilmgg"
    )

    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute(query)
    raw_data = mycursor.fetchall()
    return pd.DataFrame(raw_data)
    
query = f'''
Select t1.id assessment_id, t1.start_datetime, t1.closing_datetime, t1.duration, t1.proctored,
c.course_code, cv.course_name, cv.course_credits, t7.registration_id, concat(t7.f_name, ' ', t7.l_name) student_name, t5.programme_name, 
concat("R",t6.row_number, "C", t6.column_number) seat_number, t9.name venue_name
from ems_assessment t1 
left join term_course t2 on t2.id = t1.term_course_id
left join course_version cv on cv.id = t2.course_version_id
left join course c on c.course_id = cv.course_id
left join ems_assessment_student t3 on t3.assessment_id = t1.id
left join ems_assessment_venue_seating t6 on t3.venue_seating_id = t6.id
left join ems_assessment_venue_infrastructure t8 on t8.id = t6.assessment_venue_infrastructure_id
left join infrastructure_version t9 on t9.id = t8.infrastructure_id
left join user_attributes t7 on t7.ukid = t3.ukid
left join student_profile t4 on t4.ukid = t3.ukid
left join programme t5 on t5.programme_id = t4.programme_id
where date(start_datetime) = curdate() +1
group by t1.id, t2.id, t3.id
order by start_datetime asc;
'''


# fetching data from query to df
df = fetch_data(query)
df['duration'] = (
    df['duration']
    .astype(str)
    .str.extract(r'(\d{2}:\d{2}:\d{2})', expand=False)
)


# Create an empty list to store error messages
error_logs = []


# Save error logs to Excel
df.to_excel(f'C:/Users/suraj/OneDrive/Desktop/IILMGG Seating Plan {(pd.Timestamp.now()).strftime("%Y-%m-%d %H-%M")}.xlsx', index=False)