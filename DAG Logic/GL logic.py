import pandas as pd

# Load the CSV file
file_path = "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\gatepass raw full.csv"  # Replace with your file path
df = pd.read_csv(file_path)

# Convert punch to datetime and sort
df['punch'] = pd.to_datetime(df['punch'], dayfirst=True)
df = df.sort_values(by=['ukid', 'punch']).reset_index(drop=True)

# Collect rows with same device_name consecutively
consecutive_rows = []

for i in range(len(df) - 1):
    current = df.iloc[i]
    next_row = df.iloc[i + 1]
    if current['ukid'] == next_row['ukid'] and current['device_name'] == next_row['device_name']:
        consecutive_rows.append(current)
        consecutive_rows.append(next_row)

# Remove duplicates
result_df = pd.DataFrame(consecutive_rows).drop_duplicates().reset_index(drop=True)

# Export
result_df.to_csv("C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\GL_consecutive_device.csv", index=False)
print("✅ Saved to 'consecutive_device_fixed3.csv'")
