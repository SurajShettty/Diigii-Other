import pandas as pd

# Read data
df = pd.read_csv(r"C:\Users\suraj\OneDrive\Desktop\input.csv")

# Convert date columns to datetime
df['student_added_to_class'] = pd.to_datetime(df['student_added_to_class'], format='ISO8601')
df['start'] = pd.to_datetime(df['start'], format='ISO8601')

# Apply filtering
def filter_logic(row):
    if row['consider_attendance_from'] == 'STUDENT_DATE_OF_JOINING_CLASSGROUP':
        return row['student_added_to_class'] <= row['start']
    elif row['consider_attendance_from'] == 'START_DATE_OF_CLASSGROUP':
        return True
    else:
        return False

filtered_df = df[df.apply(filter_logic, axis=1)]

# Save to Excel
output_file = r"C:\Users\suraj\OneDrive\Desktop\output.csv"
filtered_df.to_csv(output_file, index=False)

print(f"Filtered data saved to {output_file}")
