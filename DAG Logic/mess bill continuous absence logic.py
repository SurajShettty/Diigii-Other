"""
Mess bill calculation based on continuous/consecutive absent days from Hostel Attendance data.

Rule: reduction = n - 5, where n = length of a continuous run of absent days (n > 5).
Intermittent absences (with gaps) are NOT combined - only a truly consecutive run counts.
Only the single longest continuous absent block in a month is used for the reduction
(set ONLY_CONSIDER_LONGEST_BLOCK = False to instead sum the reduction of every
qualifying block in the month).
"""

import pandas as pd

# ----------------------- CONFIG -----------------------
INPUT_FILE = r"C:\Users\suraj\Downloads\hostel_attendance_datewise_report.xlsx"
OUTPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\mess_bill_report.xlsx"

MIN_CONTINUOUS_DAYS = 5          # reduction only applies when a run is MORE than this
ONLY_CONSIDER_LONGEST_BLOCK = True

# Values in the status column that mean "absent". Matched case-insensitively.
# The script prints the unique status values it found - update this list to match.
ABSENT_STATUS_VALUES = ["ABSENT"]

# Candidate column names to auto-detect the actual headers in the input file.
UKID_CANDIDATES = ["ukid", "occupant_ukid", "student_ukid"]
DATE_CANDIDATES = ["attendance_for_date", "attendance_for", "attendance_date", "date"]
STATUS_CANDIDATES = ["status"]
BUILDING_CANDIDATES = ["building"]
FLOOR_CANDIDATES = ["floor_name"]
ROOM_CANDIDATES = ["room"]
# --------------------------------------------------------


def find_column(df, candidates):
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    for cand in candidates:
        for col_lower, col_actual in cols_lower.items():
            if cand.lower() in col_lower:
                return col_actual
    return None


def get_continuous_blocks(dates):
    """dates: sorted list of unique date objects. Returns list of (start, end, length)."""
    if not dates:
        return []
    blocks = []
    block_start = dates[0]
    prev = dates[0]
    for d in dates[1:]:
        if (d - prev).days == 1:
            prev = d
            continue
        blocks.append((block_start, prev, (prev - block_start).days + 1))
        block_start = d
        prev = d
    blocks.append((block_start, prev, (prev - block_start).days + 1))
    return blocks


def main():
    df = pd.read_excel(INPUT_FILE)

    ukid_col = find_column(df, UKID_CANDIDATES)
    date_col = find_column(df, DATE_CANDIDATES)
    status_col = find_column(df, STATUS_CANDIDATES)
    building_col = find_column(df, BUILDING_CANDIDATES)
    floor_col = find_column(df, FLOOR_CANDIDATES)
    room_col = find_column(df, ROOM_CANDIDATES)

    if not ukid_col or not date_col or not status_col:
        raise ValueError(
            f"Could not auto-detect required columns. "
            f"ukid={ukid_col}, date={date_col}, status={status_col}. "
            f"Available columns: {list(df.columns)}"
        )

    print(f"Using columns -> ukid: '{ukid_col}', date: '{date_col}', status: '{status_col}'")
    print(f"Unique status values found: {sorted(df[status_col].dropna().unique().tolist())}")

    df[date_col] = pd.to_datetime(df[date_col])
    df["_month"] = df[date_col].dt.to_period("M")
    df["_is_absent"] = df[status_col].astype(str).str.strip().str.upper().isin(
        [v.upper() for v in ABSENT_STATUS_VALUES]
    )

    rows = []
    for (ukid, month), group in df.groupby([ukid_col, "_month"]):
        days_in_month = month.days_in_month

        absent_dates = sorted(group.loc[group["_is_absent"], date_col].dt.date.unique().tolist())
        blocks = get_continuous_blocks(absent_dates)
        qualifying_blocks = [b for b in blocks if b[2] > MIN_CONTINUOUS_DAYS]

        if not qualifying_blocks:
            reduction_days = 0
            longest_block_len = max((b[2] for b in blocks), default=0)
        elif ONLY_CONSIDER_LONGEST_BLOCK:
            longest_block = max(qualifying_blocks, key=lambda b: b[2])
            reduction_days = longest_block[2] - MIN_CONTINUOUS_DAYS
            longest_block_len = longest_block[2]
        else:
            reduction_days = sum(b[2] - MIN_CONTINUOUS_DAYS for b in qualifying_blocks)
            longest_block_len = max(b[2] for b in qualifying_blocks)

        mess_days_applicable = days_in_month - reduction_days

        blocks_desc = "; ".join(
            f"{b[0]} to {b[1]} ({b[2]}d)" for b in blocks
        )

        latest_row = group.sort_values(date_col).iloc[-1]

        rows.append({
            "ukid": ukid,
            "month": str(month),
            "building": latest_row[building_col] if building_col else None,
            "floor_name": latest_row[floor_col] if floor_col else None,
            "room": latest_row[room_col] if room_col else None,
            "total_days_in_month": days_in_month,
            "total_absent_days": len(absent_dates),
            "continuous_absent_blocks": blocks_desc,
            "longest_continuous_absent_days": longest_block_len,
            "reduction_days": reduction_days,
            "mess_days_applicable": mess_days_applicable,
        })

    report = pd.DataFrame(rows).sort_values(["ukid", "month"])

    cols = ["ukid", "month", "building", "floor_name", "room", "total_days_in_month",
            "total_absent_days", "continuous_absent_blocks",
            "longest_continuous_absent_days", "reduction_days", "mess_days_applicable"]
    optional_col_available = {"building": building_col, "floor_name": floor_col, "room": room_col}
    cols = [c for c in cols if c not in optional_col_available or optional_col_available[c]]
    report = report[cols]

    report.to_excel(OUTPUT_FILE, index=False)
    print(f"Mess bill report saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
