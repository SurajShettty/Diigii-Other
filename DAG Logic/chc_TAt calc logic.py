import pandas as pd
import datetime as dt
import numpy as np

requests = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\requests.csv")
working_hours = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\working_hours.csv")
# select * from chc_service_working_hours where is_active = 1

requests["request_date"] = pd.to_datetime(requests["request_date"])
requests["resolved_on"] = pd.to_datetime(requests["resolved_on"])

working_hours["start_time"] = pd.to_timedelta(working_hours["start_time"])
working_hours["end_time"] = pd.to_timedelta(working_hours["end_time"])

# Map weekdays (convert MONDAY → 0, etc.)
weekday_map = {
    "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2,
    "THURSDAY": 3, "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6
}
working_hours["weekday"] = working_hours["day"].map(weekday_map)

def calc_tat(row, wh_table):

    # Check if working hours are enabled
    if row.get("working_hours_enabled", 0) == 0:
        # Calculate normal difference
        return (row["resolved_on"] - row["request_date"]) // pd.Timedelta(minutes=1)


    # Otherwise: use working hours logic
    service_id = row["service_id"]
    start = row["request_date"]
    end = row["resolved_on"]

    total_minutes = 0

    # Working hours for this service only
    wh_service = wh_table[wh_table["service_id"] == service_id]

    # Loop through each day between request and resolution
    current_day = start.normalize()
    last_day = end.normalize()

    while current_day <= last_day:
        weekday = current_day.weekday()

        # Working hours for this weekday
        wh_day = wh_service[wh_service["weekday"] == weekday]

        # If working hours exist
        for _, w in wh_day.iterrows():

            work_start = current_day + w["start_time"]
            work_end = current_day + w["end_time"]

            overlap_start = max(start, work_start)
            overlap_end = min(end, work_end)

            if overlap_end > overlap_start:
                total_minutes += (overlap_end - overlap_start) // pd.Timedelta(minutes=1)


        current_day += pd.Timedelta(days=1)

    return total_minutes

requests["tat_minutes"] = requests.apply(
    lambda r: calc_tat(r, working_hours) if str(r.get("status", "")).strip().lower() == "closed" else np.nan,
    axis=1
)

# Round tat_minutes to 2 decimal places
requests["tat_minutes"] = requests["tat_minutes"].round(2)

requests.to_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\tat_output.csv", index=False)