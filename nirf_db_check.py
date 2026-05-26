import mysql.connector
import pandas as pd

db_config = {
    "host": "collpolldb10-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    "user": "suraj_shetty",
    "password": "SEaucTgQZg",
    "database": "collpoll_university"
}

conn = mysql.connector.connect(**db_config)
cur = conn.cursor()

# Keywords to look for tables relevant to NIRF TLR parameters
keyword_groups = {
    "Faculty / Staff": ["faculty", "staff", "employee", "teacher", "qualification", "phd", "experience"],
    "Student Enrolment": ["student", "enroll", "programme", "admission", "batch"],
    "Finance / Budget": ["budget", "finance", "expenditure", "fund", "grant", "fee", "salary", "payment"],
    "Infrastructure": ["classroom", "room", "lab", "library", "book", "journal", "hostel", "infra", "facility", "building", "bandwidth", "internet"],
    "Research": ["research", "publication", "patent", "project"]
}

cur.execute("SHOW TABLES")
all_tables = [r[0] for r in cur.fetchall()]
print(f"Total tables in collpoll_university: {len(all_tables)}\n")

results = {}
for group, kws in keyword_groups.items():
    matched = sorted({t for t in all_tables for k in kws if k in t.lower()})
    results[group] = matched
    print(f"=== {group} ({len(matched)} tables) ===")
    for t in matched:
        print(f"  - {t}")
    print()

# Save full table list for reference
pd.DataFrame({"table_name": all_tables}).to_csv(
    r"C:\Users\suraj\Downloads\Diigii-Other\collpoll_university_tables.csv", index=False)

conn.close()
print("Done. Full table list saved to collpoll_university_tables.csv")
