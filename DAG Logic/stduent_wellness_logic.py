import pandas as pd
import math


# =========================================================
# CONFIG: SET YOUR FILE PATHS HERE
# =========================================================

INPUT_FILE_PATH = r"C:\Users\suraj\OneDrive\Desktop\student_sample_input_50.xlsx"
OUTPUT_FILE_PATH = r"C:\Users\suraj\OneDrive\Desktop\student_sample_output_with_scores.xlsx"


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

    if days_skipped <= 4:
        return 0
    return round((days_skipped - 4) ** 1.5, 2)


def exponential_meal_skip_score(meals_skipped):
    try:
        meals_skipped = int(meals_skipped)
    except:
        meals_skipped = 0

    if meals_skipped <= 2:
        return 0
    return round(3 ** (meals_skipped - 2), 2)


# =========================================================
# Engagement Score (RAW)
# =========================================================

def calculate_engagement_score(row):
    score = 0

    score += capped_score(row.get('No of assessments submitted', 0), 10, 0.6)
    score += capped_score(row.get('Total no of events participated', 0), 8, 0.3)

    score += diminishing_score(row.get('No of campus feed posts acknowledged', 0), 0.4)
    score += diminishing_score(row.get('No of comments posted', 0), 0.3)

    score += capped_score(row.get('No of other campus services used', 0), 6, 0.3)

    mentor = row.get('No. of mentor counselling requests', 0)
    if 1 <= mentor <= 4:
        score += 2
    elif mentor > 6:
        score -= 1

    score += capped_score(row.get('No. of gate movements', 0), 30, 0.05)
    score += capped_score(row.get('No. of fitness services availed/booked', 0), 10, 0.2)
    score += capped_score(row.get('No of marketplace purchases', 0), 10, 0.1)

    score += diminishing_score(row.get('No. of job opportunity applications', 0), 0.6)

    # Negative behaviours
    score -= capped_score(row.get('No of malpractice status marked', 0), 3, 2)
    score -= capped_score(row.get('No. of times fees paid late', 0), 5, 0.7)
    score -= capped_score(row.get('No of times entered late', 0), 10, 0.4)

    return round(score, 2)


# =========================================================
# Stress Score (RAW)
# =========================================================

def calculate_stress_score(row):
    score = 0

    score += exponential_class_skip_score(
        row.get('Total no of consecutive classes skipped in a month', 0)
    )

    score += exponential_meal_skip_score(
        row.get("Last 'n' consecutive meals not availed", 0)
    )

    score += row.get('No. of grievance services requested', 0) * 3
    score += row.get('Total no. of backlog courses', 0) * 2
    score += row.get('Total no. of exams missed', 0) * 1

    # Financial stress (scaled)
    score += capped_score(row.get('Total uncleared dues', 0), 100000, 0.00005)

    # Placement pressure
    job_selections = row.get('No. of job selections', 0)
    job_rejections = row.get('No. of job rejections', 0)

    if job_selections > 0:
        score -= job_selections * 3
    else:
        score += job_rejections * 2

    # Mental health support reduces stress
    score -= row.get('No. of mental health counselling requests', 0) * 2

    return round(score, 2)


# =========================================================
# Wellness Score (RAW)
# =========================================================

def calculate_wellness_score(engagement, stress):
    return round(engagement - stress, 2)


# =========================================================
# Job Rejection Rate
# =========================================================

def calculate_job_rejection_rate(row):
    rejections = row.get('No. of job rejections', 0)
    selections = row.get('No. of job selections', 0)

    total = rejections + selections
    if total == 0:
        return 0

    return round(rejections / total, 2)


# =========================================================
# Normalization (0–100)
# =========================================================

def normalize_series(series):
    min_val = series.min()
    max_val = series.max()

    if max_val == min_val:
        return pd.Series([50] * len(series), index=series.index)

    return ((series - min_val) / (max_val - min_val)) * 100


# =========================================================
# Main processing
# =========================================================

def process_student_wellness(input_path, output_path):
    df = pd.read_excel(input_path)

    # Raw scores
    df['Engagement Score'] = df.apply(calculate_engagement_score, axis=1)
    df['Stress Score'] = df.apply(calculate_stress_score, axis=1)
    df['Wellness Score'] = df.apply(
        lambda r: calculate_wellness_score(
            r['Engagement Score'], r['Stress Score']
        ),
        axis=1
    )
    df['Job Rejection Rate'] = df.apply(calculate_job_rejection_rate, axis=1)

    # Normalized scores (added at the END)
    df['Engagement Score (Normalized)'] = normalize_series(df['Engagement Score']).round(2)
    df['Stress Score (Normalized)'] = normalize_series(df['Stress Score']).round(2)
    df['Wellness Score (Normalized)'] = (
        df['Engagement Score (Normalized)'] -
        df['Stress Score (Normalized)']
    ).round(2)

    # Save to Excel
    df.to_excel(output_path, index=False)

    print("✅ Processing complete")
    print(f"📥 Input : {input_path}")
    print(f"📤 Output: {output_path}")

    return df


# =========================================================
# Run
# =========================================================

if __name__ == "__main__":
    process_student_wellness(INPUT_FILE_PATH, OUTPUT_FILE_PATH)
