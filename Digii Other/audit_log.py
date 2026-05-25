import mysql.connector
import pandas as pd

# DB connection
conn = mysql.connector.connect(
    host="collpolldb18-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    user="suraj_shetty",
    password="tttUVwa1nM",
    database="collpoll_rec"
)

cursor = conn.cursor(dictionary=True)

# User inputs
action_input = input("Enter action: ").strip()
keyword_input = input("Enter keyword to search in current_value JSON: ").strip().lower()

# Query
query = """
select al.*,ua.registration_id,concat(ua.f_name," ",ua.l_name) as activity_performed_by from audit_log al inner join user_attributes ua on ua.ukid = al.ukid
WHERE action = %s
AND LOWER(current_value) LIKE %s
ORDER BY timestamp
"""

cursor.execute(query, (action_input, f"%{keyword_input}%"))

rows = cursor.fetchall()

# Output row by row
if not rows:
    print("\nNo matching records found.")
else:
    print("\nMatching Records:\n")
    
    for i, row in enumerate(rows, start=1):
        print(f"----- Record {i} -----")
        print(f"Registration ID       : {row['registration_id']}")
        print(f"Activity Performed By : {row['activity_performed_by']}")
        print(f"Timestamp             : {row['timestamp']}")
        print(f"Current Value         : {row['current_value']}")
        print(f"Previous Value         : {row['previous_value']}")
        print("\n")

# Close connection
cursor.close()
conn.close()