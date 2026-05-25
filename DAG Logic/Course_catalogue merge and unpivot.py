import pandas as pd

# File paths
file_paths = [
    "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\1.csv",
    "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\2.csv",
    "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\3.csv",
    "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\4.csv",
    "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\5.csv",
    "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\6.csv",
    "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\7.csv"
]

# Load and merge
merged_df = pd.read_csv(file_paths[0], encoding='ISO-8859-1')
for file in file_paths[1:]:
    df = pd.read_csv(file, encoding='ISO-8859-1')
    merged_df = pd.merge(merged_df, df, on='term_course_id', how='left')


# Melt the last 3 columns into long format
melted_df = pd.melt(
    merged_df,
    id_vars=[col for col in merged_df.columns if col not in ['no_of_classes', 'course_credits_y', 'cwa_breakup']],
    value_vars=['no_of_classes', 'course_credits_y', 'cwa_breakup'],
    var_name='level1',
    value_name='value'
)

# Map technical column names to display names
melted_df['level1'] = melted_df['level1'].map({
    'no_of_classes': 'no of class group created',
    'course_credits_y': 'Credits',
    'cwa_breakup': 'cwa'
})

# Add `level2` from 'type' column
melted_df['level2'] = melted_df['type']


# Reorder columns (optional)
cols = [col for col in merged_df.columns if col not in ['no_of_classes', 'course_credits_y', 'cwa_breakup']] + ['level1', 'level2', 'value']
final_df = melted_df[cols]

# Save the final result
final_df.to_csv("C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\final_unpivotedd.csv", index=False)

print("Final unpivoted CSV saved as 'final_unpivoted.csv'")

