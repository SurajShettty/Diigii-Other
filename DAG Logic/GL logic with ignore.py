import pandas as pd

# Load the CSV file
file_path = "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\dddd.csv"
df = pd.read_csv(file_path)

# Convert punch to datetime and sort
df['punch'] = pd.to_datetime(df['punch'], dayfirst=True)
df = df.sort_values(by=['ukid', 'punch']).reset_index(drop=True)

consecutive_rows = []

# Group by ukid
for ukid, group in df.groupby('ukid'):
    group = group.reset_index(drop=True)
    n = len(group)
    
    i = 0
    while i < n - 1:
        curr = group.loc[i]
        j = i + 1
        temp_sequence = [curr]
        
        while j < n:
            next_row = group.loc[j]
            
            # Handle case when next row is 'ignore'
            if 'ignore' in str(next_row['device_name']).lower() or 'failed' in str(next_row['device_name']).lower():
                temp_sequence.append(next_row)
                j += 1
                continue
            
            # If same device as current (ignoring any 'ignore' rows in between)
            if curr['device_name'] == next_row['device_name']:
                temp_sequence.append(next_row)
                # Store this block only if it has at least 2 of same device rows (ignore rows in between allowed)
                if len([r for r in temp_sequence if not any(x in str(r['device_name']).lower() for x in ['ignore', 'fail'])]) > 1:
                    consecutive_rows.extend(temp_sequence)
                break
            else:
                break  # Different device_name → stop

        i += 1



# Remove duplicates and reset index
result_df = pd.DataFrame(consecutive_rows).drop_duplicates().reset_index(drop=True)
# # Format punch column to include seconds
# result_df['punch'] = result_df['punch'].dt.strftime('%Y-%m-%d %H:%M:%S')

# Export to CSV
output_path = "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\SNU_consecutive_device_with_ignore_fail full.csv"
result_df.to_csv(output_path, index=False)
print("✅ Saved to 'SNU_consecutive_device_with_ignore.csv'")
