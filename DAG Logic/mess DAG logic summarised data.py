import pandas as pd

# 1. Load datasets
user_mess = pd.read_csv(r'C:\Users\suraj\OneDrive\Desktop\user_mess.csv')
mess_schedule = pd.read_csv(r'C:\Users\suraj\OneDrive\Desktop\mess_schedule.csv')
availed = pd.read_csv(r'C:\Users\suraj\OneDrive\Desktop\availed.csv')

# 2. Base (current user → schedule combos)
base = pd.merge(user_mess, mess_schedule, on='mess_id', how='inner')

# 3. Include availed with schedule info (for removed users)
availed_enriched = pd.merge(
    availed,
    mess_schedule[['mess_schedule_id', 'date', 'meal', 'mess', 'mess_id']],
    on='mess_schedule_id',
    how='left'
)

# 4. Outer merge base + availed
merged = pd.merge(
    base,
    availed_enriched,
    how='outer',
    on=['ukid', 'mess_schedule_id'],
    suffixes=('_base', '_availed')
)

# 5. Coalesce schedule columns
for col in ['date', 'meal', 'mess', 'mess_id']:
    merged[col] = merged[f'{col}_base'].fillna(merged[f'{col}_availed'])

# 6. Consolidate meal_availed_count & flag
merged['meal_availed_count'] = merged.filter(like='meal_availed_count').sum(axis=1).fillna(0).astype(int)
merged['meal_availed_flag'] = merged['meal_availed_count'].gt(0).map({True: 'Yes', False: 'No'})

# 7. Group + Pivot
agg = merged.groupby(['date', 'meal', 'mess', 'meal_availed_flag']).agg(
    students=('ukid', 'nunique'),
    meals=('meal_availed_count', 'sum')
).reset_index()

pivot = agg.pivot_table(
    index=['date', 'meal', 'mess'],
    columns='meal_availed_flag',
    values=['students', 'meals'],
    fill_value=0
)

pivot.columns = [f"{v}_{f}" for v, f in pivot.columns]
pivot = pivot.reset_index().rename(columns={
    'students_Yes': 'students_availed',
    'meals_Yes': 'meals_availed',
    'students_No': 'students_not_availed'
})

for col in ['students_availed', 'meals_availed', 'students_not_availed']:
    if col not in pivot.columns:
        pivot[col] = 0

# 8. Export
pivot[['date', 'meal', 'mess', 'students_availed', 'meals_availed', 'students_not_availed']].to_excel(
    r'C:\Users\suraj\OneDrive\Desktop\meal_summary_report.xlsx', index=False
)

print("✅ Summary report generated successfully: 'meal_summary_report.xlsx'")
