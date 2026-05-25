import pandas as pd

# ===============================
# Function: Weighted Attendance
# ===============================
def weighted_attendance(df, group_cols, new_col_name):
    """
    Calculate weighted attendance percentage for given group (student-level).
    Formula = (sum(present) / sum(total_class_consider_for_attendance)) * 100
    """
    agg = df.groupby(group_cols).apply(
        lambda g: (g["present"].sum() / g["total_class_consider_for_attendance"].sum()) * 100
        if g["total_class_consider_for_attendance"].sum() > 0 else 0
    ).reset_index(name=new_col_name)

    # Round to 2 decimals
    agg[new_col_name] = agg[new_col_name].round(2)
    return agg


# ===============================
# Main Function
# ===============================
def add_multilevel_attendance(file_path, export_path=None):
    # Load data
    df = pd.read_csv(file_path)

    # Student-level groupings
    class_att   = weighted_attendance(df, ["ukid", "class_id"], "attendance_class_%")
    course_att  = weighted_attendance(df, ["ukid", "course_code"], "attendance_course_%")
    term_att    = weighted_attendance(df, ["ukid", "term"], "attendance_term_%")

    dept_att    = weighted_attendance(df, ["ukid", "course_dept"], "attendance_dept_%")

    # Merge into original df
    merged_df = (
        df.merge(class_att, on=["ukid", "class_id"], how="left")
          .merge(course_att, on=["ukid", "course_code"], how="left")
          .merge(term_att, on=["ukid", "term"], how="left")

          .merge(dept_att, on=["ukid", "course_dept"], how="left")
    )

    # Export if path is given
    if export_path:
        merged_df.to_csv(export_path, index=False)
        print(f"✅ Exported with new columns to {export_path}")

    return merged_df


# ===============================
# Example Usage
# ===============================
file_path = "C:\\Users\\suraj\\OneDrive\\Desktop\\IITM attendance 21-11-2025.csv"
output_path = "C:\\Users\\suraj\\OneDrive\\Desktop\\IITM attendance 21-11-2025 output.csv"
final_df = add_multilevel_attendance(file_path, export_path=output_path)
# print(final_df.head())
