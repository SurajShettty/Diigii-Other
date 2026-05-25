import pandas as pd
import numpy as np

# --- 1. Setup and Initial Data Loading ---
input_path = r"C:\Users\shami\Downloads\JIET Relative Grading Input sheet BCA.csv"
output_path = r"C:\Users\shami\Downloads\JIET Relative Grading Output sheet BCA.csv"

# Load the data
df_main = pd.read_csv(input_path, encoding='cp1252')

# List to hold the results for each course
graded_course_dfs = []

# --- 2. Define Helper Functions (No Change) ---

# Function to extract max marks based on the examination schema
def get_max_marks(schema):
    if pd.isna(schema):
        return np.nan, np.nan
    schema_str = str(schema)
    if "30-70" in schema_str:
        # max_internal, max_external
        return 30, 70
    elif "60-40" in schema_str:
        # max_internal, max_external
        return 60, 40
    else:
        return np.nan, np.nan

# Function to check eligibility based on marks and component type
def is_eligible(row):
    # Check for NaN values before comparison
    if pd.isna(row['external_marks']) or pd.isna(row['internal_marks']) or \
       pd.isna(row['max_external']) or pd.isna(row['max_internal']):
        return False

    if row['COMPONENT'] == 'LECTURE':
        # LECTURE: Only external marks eligibility check
        return row['external_marks'] >= 0.30 * row['max_external']
    elif row['COMPONENT'] == 'PRACTICAL':
        # PRACTICAL: Both external and internal marks eligibility check
        return (
            row['external_marks'] >= 0.35 * row['max_external'] and
            row['internal_marks'] >= 0.35 * row['max_internal']
        )
    else:
        return False

# Function to determine Grade and Grade Point based on Xi
def get_grade_and_points(row):
    if not row['is_eligible']:
        return 'F', 0
    xi = row['Xi']
    if pd.isna(xi): # Safety check for NaN Xi
        return 'AB', 0

    if xi >= 90:
        return 'O', 10
    elif 80 <= xi < 90:
        return 'A+', 9
    elif 70 <= xi < 80:
        return 'A', 8
    elif 60 <= xi < 70:
        return 'B+', 7
    elif 50 <= xi < 60:
        return 'B', 6
    elif 45 <= xi < 50:
        return 'C', 5
    elif 40 <= xi < 45:
        return 'P', 4
    elif xi < 40:
        return 'F', 0
    else:
        # Fallback for unexpected values
        return 'AB', 0

# Function to determine p_max based on PAbsMax

def get_p_max(PAbsMax):
    if pd.isna(PAbsMax):
        return None
    if 90 <= PAbsMax <= 100:
        return 90
    elif 80 <= PAbsMax < 90:
        return 80
    elif 70 <= PAbsMax < 80:
        return 70
    elif 60 <= PAbsMax < 70:
        return 60
    elif 50 <= PAbsMax < 60:
        return 50
    elif 40 <= PAbsMax < 50:
        return 40
    elif 30 <= PAbsMax < 40:
        return 30
    else:
        return None

# Function to determine q based on p_max
def get_q(p_max):
    if p_max is None or pd.isna(p_max):
        return None
    elif p_max >= 75:
        return 100
    elif 60 <= p_max < 75:
        return 89
    elif 30 <= p_max < 60:
        return 79
    else:
        return None

# --- 3. Iterate and Apply Grading Logic Per Course ---

# Group the main DataFrame by 'course_code'
grouped = df_main.groupby('course_code')

# Loop through each group (i.e., each unique course)
for course_code, df_course in grouped:
    # IMPORTANT: Create a copy to avoid SettingWithCopyWarning
    df = df_course.copy()

    print(f"Processing course: {course_code} ({len(df)} students)")

    # 1. Apply Ceil to Marks (Rounding up)
    df['external_marks'] = np.ceil(df['external_marks'])
    df['internal_marks'] = np.ceil(df['internal_marks'])

    # 2. Extract Max Marks
    df[['max_internal', 'max_external']] = df['exam_schema'].apply(
        lambda x: pd.Series(get_max_marks(x))
    )

    # 3. Determine Eligibility
    df['is_eligible'] = df.apply(is_eligible, axis=1)

    # 4. Calculate Topper Marks (Crucial: only among eligible students IN THIS COURSE)
    # Check if there are any eligible students for the course
    if df['is_eligible'].any():
        topper = df.loc[df['is_eligible'], 'total_marks'].max()
    else:
        # If no students are eligible, set topper to NaN or 0 to handle subsequent calculations
        topper = np.nan # Use NaN to force PAbsMax to NaN for this course

    # 5. Calculate PAbsMax (Should be NaN if topper is NaN)
    df['PAbsMax'] = round((topper / df['maximum_marks']) * 100, 2) if pd.notnull(topper) else np.nan

    # 6. Calculate Pi
    df['Pi'] = round((df['total_marks'] / df['maximum_marks']) * 100, 2)
    df['Pi'] = np.ceil(df['Pi'])    

    # 7. Calculate P_max and Q
    df['p_max'] = df['PAbsMax'].apply(get_p_max)
    df['q'] = df['p_max'].apply(get_q)

    # 8. Calculate Xi
    df['Xi'] = df.apply(
        lambda row: np.ceil((row['Pi'] / row['p_max']) * row['q'])
        if pd.notnull(row['p_max']) and pd.notnull(row['q']) and row['is_eligible']
        else np.nan,
        axis=1
    )
    df['Xi'] = np.ceil(df['Xi'])

    # 9. Determine Final Grade and Grade Point
    df[['Grade', 'Grade_Point']] = df.apply(
        lambda row: pd.Series(get_grade_and_points(row)), axis=1
    )

    # Append the graded course DataFrame to the list
    graded_course_dfs.append(df)

# --- 4. Merge and Export Final Data ---

if graded_course_dfs:
    # Concatenate all the individual course DataFrames back into one
    df_final = pd.concat(graded_course_dfs, ignore_index=True)

    # Export the final combined DataFrame
    df_final.to_csv(output_path, index=False)
    print("\n--- Script Complete ---")
    print(f"Total processed records: {len(df_final)}")
    print(f"Graded data for all courses has been saved to '{output_path}'")
else:
    print("No data found to process.")