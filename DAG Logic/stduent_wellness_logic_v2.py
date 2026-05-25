import pandas as pd
import math
import re


SERVICES_FILE = r"C:\Users\suraj\OneDrive\Desktop\wellness\services.csv"
ATTENDANCE_FILE = r"C:\Users\suraj\OneDrive\Desktop\wellness\attendance_base_summary.csv" #pipeline

OTHER_KPI_FILES = [
    r"C:\Users\suraj\OneDrive\Desktop\wellness\event_participant.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\posts.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\comments.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\movements.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\marketplace_purchases.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\last_n_consecutive_meals_not_availed.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\job_selected.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\job_not_selected.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\active_backlogs.csv", #pipeline
    r"C:\Users\suraj\OneDrive\Desktop\wellness\uncleared_due.csv", #pipeline
    r"C:\Users\suraj\OneDrive\Desktop\wellness\missed_exams.csv", #pipeline
    r"C:\Users\suraj\OneDrive\Desktop\wellness\job_applications.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\malpractice_count.csv", #pipeline
    r"C:\Users\suraj\OneDrive\Desktop\wellness\late_entries.csv",
    r"C:\Users\suraj\OneDrive\Desktop\wellness\fees_late_paid.csv", #pipeline
]

ZERO_OK_COLUMNS = [
    "No. of mentor counselling requests",
    "No. of fitness services availed/booked",
    "No. of grievance services requested",
    "No. of mental health counselling requests",
    "No of other campus services used",
    "event_participant",
    "posts",
    "comments",
    "movements",
    "No of assessments submitted"
]

DO_NOT_FILL_COLUMNS = [
    "last_n_consecutive_meals_not_availed",
    "job_selected",
    "job_not_selected",
    "job_applications",
    "marketplace_purchases",
    "active_backlogs",
    "missed_exams",
    "malpractice_count",
    "fees_late_paid",
    "late_entries",
    "uncleared_due"
]

OUTPUT_FILE_PATH = r"C:\Users\suraj\OneDrive\Desktop\student_sample_output_with_scores_v2.xlsx"

KEY_COLUMN = "ukid"

# =========================================================
# SERVICES FILE PROCESSING
# =========================================================

def calculate_last_n_consecutive_absent_days(path, key="ukid"):
    df = pd.read_csv(path)

    # Parse date safely (DD-MM-YYYY or mixed)
    df["lesson_date"] = pd.to_datetime(
        df["lesson_date"],
        dayfirst=True,
        errors="coerce"
    ).dt.date

    # Create daily_attendance equivalent
    daily_attendance = (
        df.assign(is_absent=df["final_status"].astype(str).str.upper().eq("ABSENT").astype(int))
          .groupby([key, "lesson_date"], as_index=False)["is_absent"]
          .max()   # if any ABSENT that day → 1
    )

    # Order latest → oldest
    daily_attendance = daily_attendance.sort_values(
        [key, "lesson_date"], ascending=[True, False]
    )

    # break_flag = cumulative count of PRESENT days while going backwards
    daily_attendance["break_flag"] = (
        daily_attendance.groupby(key)["is_absent"]
        .apply(lambda x: (x == 0).cumsum())
        .reset_index(drop=True)
    )

    # keep only continuous ABSENT block
    consecutive_absent = daily_attendance[
        (daily_attendance["is_absent"] == 1) &
        (daily_attendance["break_flag"] == 0)
    ]

    # count per ukid
    result = (
        consecutive_absent
        .groupby(key)
        .size()
        .reset_index(name="last_n_consecutive_absent_days")
    )

    return result



def process_services_file(path):
    df = pd.read_csv(path)

    df["service_title"] = df["service_title"].astype(str).str.lower()

    patterns = {
        "No. of mentor counselling requests": r"(mentor|mentoring|mentee|proctor counselling|student counselling|counselling|counseling)",
        "No. of fitness services availed/booked": r"(fitness|gym|yoga|zumba|workout|physio|physiotherap|nutrition|diet|wellness|sports)",
        "No. of grievance services requested": r"(grievance|grievences|redressal|complaint|complaints|query/grievance|posh complaint|theft complaint|ragging)",
        "No. of mental health counselling requests": r"(mental health|psycholog|psychiatr|therapy|counsell?ing.*mental|stress|anxiety|depression)"
    }

    match_cols = []

    for col, pattern in patterns.items():
        match_col = f"_match_{col}"
        df[match_col] = df["service_title"].str.contains(pattern, regex=True, na=False)
        df[col] = df[match_col] * df["requests"]
        match_cols.append(match_col)

    df["No of other campus services used"] = (~df[match_cols].any(axis=1)) * df["requests"]

    final_columns = list(patterns.keys()) + ["No of other campus services used"]

    result = (
        df.groupby(KEY_COLUMN)[final_columns + ["requests"]]
        .sum()
        .reset_index()
    )

    result.rename(columns={"requests": "total_requests"}, inplace=True)

    return result


# =========================================================
# Helper scoring functions
# =========================================================

def capped_score(value, cap, weight):
    try:
        value = int(value)
    except:
        value = 0
    return min(max(value, 0), cap) * weight


def diminishing_score(value, weight):
    try:
        value = int(value)
    except:
        value = 0
    return math.log1p(max(value, 0)) * weight


def exponential_class_skip_score(days_skipped):
    try:
        days_skipped = int(days_skipped)
    except:
        days_skipped = 0

    days_skipped = min(days_skipped, 15)  # HARD CAP

    if days_skipped <= 4:
        return 0
    return round((days_skipped - 4) ** 1.5, 2)


def exponential_meal_skip_score(meals_skipped):
    try:
        meals_skipped = int(meals_skipped)
    except:
        meals_skipped = 0

    # convert total → average per day (assume 30 days)
    meals_per_day = meals_skipped / 30

    if meals_per_day <= 1:
        return 0

    return round(math.log1p(meals_per_day - 1) * 5, 2)




# =========================================================
# Engagement Score
# =========================================================

def calculate_engagement_score(row):
    score = 0

    score += capped_score(row.get('No of assessments submitted', 0), 10, 0.6)
    score += capped_score(row.get('event_participant', 0), 8, 0.3)

    score += diminishing_score(row.get('posts', 0), 0.4)
    score += diminishing_score(row.get('comments', 0), 0.3)

    score += capped_score(row.get('No of other campus services used', 0), 6, 0.3)

    mentor = row.get('No. of mentor counselling requests', 0)
    if 1 <= mentor <= 4:
        score += 2
    elif mentor > 6:
        score -= 1

    score += capped_score(row.get('movements', 0), 30, 0.05)
    score += capped_score(row.get('No. of fitness services availed/booked', 0), 10, 0.2)
    score += capped_score(row.get('marketplace_purchases', 0), 10, 0.1)

    score += diminishing_score(row.get('job_applications', 0), 0.6)

    if pd.notna(row.get('malpractice_count')):
        score -= capped_score(row['malpractice_count'], 3, 2)
    if pd.notna(row.get('fees_late_paid')):
        score -= capped_score(row['fees_late_paid'], 5, 0.7)
    if pd.notna(row.get('late_entries')):
        score -= capped_score(row['late_entries'], 10, 0.4)

    return round(score, 2)


# =========================================================
# Stress Score
# =========================================================

def calculate_stress_score(row):
    score = 0

    score += exponential_class_skip_score(row.get('last_n_consecutive_absent_days', 0))
    meals = row.get("last_n_consecutive_meals_not_availed", None)
    if pd.notna(meals):
        score += exponential_meal_skip_score(meals)


    score += row.get('No. of grievance services requested', 0) * 3
    if pd.notna(row.get('active_backlogs')):
        score += row['active_backlogs'] * 2
    if pd.notna(row.get('missed_exams')):
        score += row['missed_exams'] * 1

    score += capped_score(row.get('uncleared_due', 0), 100000, 0.00005)

    job_selections = row.get('job_selected', None)
    job_rejections = row.get('job_not_selected', None)

    if pd.notna(job_selections) and job_selections > 0:
        score -= job_selections * 3
    elif pd.notna(job_rejections):
        score += job_rejections * 2

    mental = row.get('No. of mental health counselling requests', None)
    if pd.notna(mental):
        score -= mental * 2

    # return round(score, 2)
    return max(round(score, 2), 0)


# =========================================================
# Normalization
# =========================================================

def normalize_series(series):
    min_val = series.min()
    max_val = series.max()

    if max_val == min_val:
        return pd.Series([50] * len(series), index=series.index)

    return ((series - min_val) / (max_val - min_val)) * 100


# =========================================================
# Merge all KPI files
# =========================================================

def load_and_merge_kpi_files(kpi_files, services_df, key='ukid'):
    dfs = [services_df]

    for path in kpi_files:
        df = pd.read_csv(path)
        dfs.append(df)

    merged = dfs[0]
    for df in dfs[1:]:
        merged = pd.merge(merged, df, on=key, how='outer')

    return merged


# =========================================================
# Main
# =========================================================

def process_student_wellness():
    services_df = process_services_file(SERVICES_FILE)

    # Calculate attendance KPI directly
    attendance_df = calculate_last_n_consecutive_absent_days(ATTENDANCE_FILE, KEY_COLUMN)

    # Load other KPI files
    df = load_and_merge_kpi_files(OTHER_KPI_FILES, services_df, KEY_COLUMN)

    # Merge attendance KPI
    df = pd.merge(df, attendance_df, on=KEY_COLUMN, how="left")


    # Fill only safe columns
    for col in ZERO_OK_COLUMNS:
        if col in df.columns:
            df[col] = df[col].fillna(0)


    df['Engagement Score'] = df.apply(calculate_engagement_score, axis=1)
    df['Stress Score'] = df.apply(calculate_stress_score, axis=1)

    df['Wellness Score'] = (df['Engagement Score'] - df['Stress Score']).round(2)

    df['Engagement Score (Normalized)'] = normalize_series(df['Engagement Score']).round(2)
    df['Stress Score (Normalized)'] = normalize_series(df['Stress Score']).round(2)
    df['Wellness Score (Normalized)'] = normalize_series(df['Wellness Score']).round(2)


    df.to_excel(OUTPUT_FILE_PATH, index=False)

    print("✅ Processing complete")
    print(f"📤 Output: {OUTPUT_FILE_PATH}")


if __name__ == "__main__":
    process_student_wellness()
