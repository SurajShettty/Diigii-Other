import pandas as pd
import math

# Load your dataset
df = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\infra test.csv")

# Convert datetime columns
df['start'] = pd.to_datetime(df['start'])
df['end'] = pd.to_datetime(df['end'])

# 🔹 FILTER: keep only rows where new_status is NULL
df = df[df['new_status'].notna()]

expanded_rows = []

for _, row in df.iterrows():
    start_time = row['start']
    end_time = row['end']
    infra_id = row['infrastructure_id']
    venue = row.get('Venue', 'Unknown')
    occupancy = row.get('occupancy_%', None)

    # Round down start to nearest hour and round up end to next hour
    start_hour = start_time.floor('H')
    end_hour = end_time.ceil('H')

    # Loop through all hours covered
    current_time = start_hour
    while current_time < end_time:
        hour_str = current_time.strftime("%I%p").lstrip("0")  # Windows-safe, e.g. "8AM"
        expanded_rows.append({
            'Infra ID': infra_id,
            'Venue': venue,
            'date': current_time.date(),
            'hour': hour_str,
            'occupancy_%': occupancy
        })
        current_time += pd.Timedelta(hours=1)

# Create new dataframe
expanded_df = pd.DataFrame(expanded_rows)

# Save to file
expanded_df.to_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\expanded_room_data.csv", index=False)
