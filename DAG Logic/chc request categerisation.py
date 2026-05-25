import pandas as pd
import re

# =========================
# FILE PATHS
# =========================
INPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\rr.csv"
OUTPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\rr_categorised.xlsx"

# =========================
# READ INPUT
# =========================
df = pd.read_csv(INPUT_FILE)

# Normalize service names
df["service_name"] = df["service_name"].astype(str).str.lower()

# =========================
# KEYWORD REGEX PATTERNS
# =========================
patterns = {
    "Mentor counselling requests": r"(mentor|mentoring|mentee|proctor counselling|student counselling|counselling|counseling)",

    "Fitness services availed/booked": r"(fitness|gym|yoga|zumba|workout|physio|physiotherap|nutrition|diet|wellness|sports)",

    "Grievance services requested": r"(grievance|grievences|redressal|complaint|complaints|query/grievance|posh complaint|theft complaint|ragging)",

    "Mental health counselling requests": r"(mental health|psycholog|psychiatr|therapy|counsell?ing.*mental|stress|anxiety|depression)"
}

# =========================
# CREATE CATEGORY COLUMNS
# =========================
match_cols = []

for col, pattern in patterns.items():
    match_col = f"_match_{col}"
    df[match_col] = df["service_name"].str.contains(pattern, regex=True, na=False)
    df[col] = df[match_col] * df["requests"]
    match_cols.append(match_col)

# =========================
# OTHERS COLUMN
# =========================
# If service_name did not match ANY category
df["Others"] = (~df[match_cols].any(axis=1)) * df["requests"]

# =========================
# AGGREGATE PER UKID
# =========================
final_columns = list(patterns.keys()) + ["Others"]

result = (
    df.groupby("ukid")[final_columns]
    .sum()
    .reset_index()
)

# =========================
# WRITE OUTPUT
# =========================
result.to_excel(OUTPUT_FILE, index=False)

print("✅ Categorised dataset with 'Others' created successfully")
