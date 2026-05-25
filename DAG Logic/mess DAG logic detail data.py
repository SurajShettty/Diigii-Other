import pandas as pd

# ------------------------------
# 1. Load Excel datasets
# ------------------------------
user_mess = pd.read_csv('C:\\Users\\suraj\\OneDrive\\Desktop\\user_mess.csv')          # Sheet containing user-mess mapping
mess_schedule = pd.read_csv('C:\\Users\\suraj\\OneDrive\\Desktop\\mess_schedule.csv')  # Sheet containing meal schedule for the day
availed = pd.read_csv('C:\\Users\\suraj\\OneDrive\\Desktop\\availed.csv')              # Sheet containing meal availed records

# ------------------------------
# 2. Cross join user_mess with mess_schedule
# ------------------------------
user_mess['key'] = 1
mess_schedule['key'] = 1
base = pd.merge(user_mess, mess_schedule, on='key').drop('key', axis=1)

# Filter only where mess_id matches between user_mess and mess_schedule
base = base[base['mess_id_x'] == base['mess_id_y']].drop(columns=['mess_id_x']).rename(columns={'mess_id_y': 'mess_id'})

# ------------------------------
# 3. Outer join with availed to include removed users
# ------------------------------
final = pd.merge(
    base,
    availed,
    how='outer',
    left_on=['ukid', 'mess_schedule_id'],
    right_on=['ukid', 'mess_schedule_id']
)

# ------------------------------
# 4. Clean up and fill missing values
# ------------------------------
final['meal_availed_count'] = final['meal_availed_count'].fillna(0).astype(int)
final['meal_availed_flag'] = final['meal_availed_count'].apply(lambda x: 'Yes' if x > 0 else 'No')

# ------------------------------
# 5. Select and rename columns
# ------------------------------
final = final[['ukid', 'mess_id', 'mess_schedule_id', 'mess', 'meal', 'date', 'meal_availed_count', 'meal_availed_flag']]

# ------------------------------
# 6. Export to Excel
# ------------------------------
final.to_excel('C:\\Users\\suraj\\OneDrive\\Desktop\\meal_report.xlsx', index=False)

print("✅ Meal report generated successfully: 'meal_report.xlsx'")
