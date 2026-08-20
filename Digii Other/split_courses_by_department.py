"""
Split course catalogue data into department-wise Excel files.

Input format (reference):
    Course Name* | Course Code* | Department | Component 1 | Hours | Credit | Component 2 | Hours | Credit | ...

Output format (reference):
    Course Name*, Alternate Name, Course Code*, Alternate Code, faculty email id,
    faculty Registration No, Description*,
    <Component 1> Credits, <Component 1> Hours, <Component 2> Credits, <Component 2> Hours, ...

Usage:
    Run the script and provide the input file path when prompted.
    Output files are written to a hardcoded folder (see OUTPUT_DIR below).
"""

import os
import re
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Hardcoded configuration
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path(r"C:\Users\suraj\Downloads\Diigii-Other\department_wise_output")
INPUT_SHEET_NAME = 0          # first sheet for Excel files
DEFAULT_HEADER_ROW = 1        # 1-based Excel row number used as header (default: first row)
OUTPUT_FILE_EXTENSION = ".xlsx"

# Output base columns that are always present (copied/left blank as applicable)
OUTPUT_BASE_COLUMNS = [
    "Course Name*",
    "Alternate Name",
    "Course Code*",
    "Alternate Code",
    "faculty email id",
    "faculty Registration No",
    "Description*",
]

# Fixed component columns in the exact order required in the output.
# Each component contributes a "<Name> Credits" and "<Name> Hours" column.
FIXED_COMPONENTS = [
    "Lecture",
    "Practical",
    "Tutorial",
    "Project Work",
    "Workshop",
    "Studio",
    "DOAP",
    "Clinical Posting",
    "Self Directed Learning",
    "Internship",
    "Experiential Learning",
    "LIT",
    "TCS",
    "Laboratory",
]

# Mapping from normalized input component names to the fixed output component names.
# Add aliases here if your input uses abbreviations or slight variations.
COMPONENT_NAME_MAP = {
    "lecture": "Lecture",
    "practical": "Practical",
    "tutorial": "Tutorial",
    "project work": "Project Work",
    "projectwork": "Project Work",
    "project": "Project Work",
    "workshop": "Workshop",
    "studio": "Studio",
    "doap": "DOAP",
    "clinical posting": "Clinical Posting",
    "clinicalposting": "Clinical Posting",
    "clinical": "Clinical Posting",
    "self directed learning": "Self Directed Learning",
    "selfdirectedlearning": "Self Directed Learning",
    "self directed": "Self Directed Learning",
    "internship": "Internship",
    "experiential learning": "Experiential Learning",
    "experientiallearning": "Experiential Learning",
    "experiential": "Experiential Learning",
    "lit": "LIT",
    "tcs": "TCS",
    "laboratory": "Laboratory",
    "lab": "Laboratory",
}

# Trailing blank columns added at the end of every output sheet
TRAILING_COLUMNS = [
    "Course focuses on Employability",
    "Course focuses on Entrepreneurship",
    "Course focuses on Skill Development",
    "Course Offers transferable skills",
    "Course Offers life skills",
    "Additional link",
]


def sanitize_filename(name: str) -> str:
    """Remove characters that are illegal in Windows file names."""
    if not isinstance(name, str):
        name = str(name)
    name = name.strip()
    # Replace common path separators and reserved characters
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    # Collapse multiple spaces/underscores
    name = re.sub(r"\s+", " ", name)
    return name


def _clean_for_matching(text: str) -> str:
    """Normalize header text for fuzzy matching."""
    text = str(text).lower().strip()
    text = text.replace("\xa0", " ")  # non-breaking space -> space
    # Remove common decorative/noise characters
    for ch in "*()[]:":
        text = text.replace(ch, " ")
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_column(df: pd.DataFrame, candidates):
    """
    Return the first column name that matches one of the candidate patterns.
    Matching is case-insensitive and ignores leading/trailing whitespace,
    non-breaking spaces, and decorative characters like * ( ) [ ] :.
    Returns None if no match is found.
    """
    cols = list(df.columns)
    for candidate in candidates:
        pattern = _clean_for_matching(candidate)
        if not pattern:
            continue
        for col in cols:
            col_clean = _clean_for_matching(col)
            # Exact match or substring match
            if pattern == col_clean or pattern in col_clean or col_clean in pattern:
                return col
    return None


def read_input_file(file_path: str, header_row_one_based: int) -> pd.DataFrame:
    """Read an Excel or CSV file into a DataFrame."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    header = max(0, header_row_one_based - 1)  # convert to 0-indexed for pandas
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(path, sheet_name=INPUT_SHEET_NAME, header=header)
    elif suffix == ".csv":
        return pd.read_csv(path, header=header)
    else:
        raise ValueError(f"Unsupported file type: {suffix!r}. Please provide .xlsx, .xls, or .csv")


def locate_component_groups(df: pd.DataFrame):
    """
    Identify component columns and their corresponding Hours / Credit columns.

    Returns a list of tuples:
        (component_col_name, hours_col_name, credit_col_name)
    """
    cols = list(df.columns)

    # Find columns that look like "Component 1", "Component2", "Component_1", etc.
    component_cols = [
        c for c in cols
        if re.search(r"component\s*\d+", str(c).lower().replace("_", " "))
    ]

    # Find columns that look like hours/credits
    hours_cols = [c for c in cols if re.search(r"hours?", str(c).lower())]
    credit_cols = [c for c in cols if re.search(r"credits?", str(c).lower())]

    groups = []
    for comp_col in component_cols:
        comp_idx = cols.index(comp_col)

        # Determine the boundary before the next component column
        next_comp_idx = len(cols)
        for other_comp in component_cols:
            if other_comp == comp_col:
                continue
            other_idx = cols.index(other_comp)
            if other_idx > comp_idx and other_idx < next_comp_idx:
                next_comp_idx = other_idx

        # Pick the Hours column that falls between this component and the next one
        candidate_hours = [
            c for c in hours_cols
            if comp_idx < cols.index(c) < next_comp_idx
        ]
        candidate_credits = [
            c for c in credit_cols
            if comp_idx < cols.index(c) < next_comp_idx
        ]

        if candidate_hours and candidate_credits:
            groups.append((comp_col, candidate_hours[0], candidate_credits[0]))

    return groups


def build_output_rows(df: pd.DataFrame, component_groups):
    """
    Transform input rows into the desired output format.

    Returns a tuple: (list_of_dicts, ordered_component_names)
    """
    # Identify key input columns (fuzzy matching)
    course_name_col = find_column(df, [
        "Course Name*(Subject Name)",
        "Course Name*",
        "Course Name",
        "Subject Name",
        "Course Title",
    ])
    course_code_col = find_column(df, [
        "Course Code*( Course code needs to be unique)",
        "Course Code*(Course code needs to be unique)",
        "Course Code*",
        "Course Code",
        "Subject Code",
        "Course ID",
    ])
    description_col = find_column(df, [
        "Description*(Description)",
        "Description*",
        "Description",
        "Course Description",
    ])

    def _normalize_component(name):
        if pd.isna(name):
            return ""
        return re.sub(r"\s+", "", str(name).lower().strip())

    output_rows = []
    for _, row in df.iterrows():
        course_name = row.get(course_name_col, "") if course_name_col else ""
        course_code = row.get(course_code_col, "") if course_code_col else ""
        description = row.get(description_col, "") if description_col else ""

        # Fallbacks: Description -> Course Name, Alternate Name -> Course Name
        if not description and course_name is not None:
            description = course_name

        out = {
            "Course Name*": course_name,
            "Alternate Name": course_name,
            "Course Code*": course_code,
            "Alternate Code": "",
            "faculty email id": "",
            "faculty Registration No": "",
            "Description*": description,
        }

        # Initialize all fixed component credit/hour columns as blank
        for comp_name in FIXED_COMPONENTS:
            out[f"{comp_name} Credits"] = ""
            out[f"{comp_name} Hours"] = ""

        # Fill in values for components present in this row
        for comp_col, hours_col, credit_col in component_groups:
            comp_name = row.get(comp_col)
            if pd.notna(comp_name):
                comp_name = str(comp_name).strip()
                if comp_name:
                    normalized = _normalize_component(comp_name)
                    mapped_name = COMPONENT_NAME_MAP.get(normalized)
                    if not mapped_name:
                        # Try a direct case-insensitive match against fixed components
                        for fixed in FIXED_COMPONENTS:
                            if fixed.lower() == comp_name.lower():
                                mapped_name = fixed
                                break
                    if mapped_name:
                        hours_val = row.get(hours_col, "")
                        credit_val = row.get(credit_col, "")
                        out[f"{mapped_name} Credits"] = credit_val if pd.notna(credit_val) else ""
                        out[f"{mapped_name} Hours"] = hours_val if pd.notna(hours_val) else ""

        output_rows.append(out)

    return output_rows, FIXED_COMPONENTS


def main():
    input_path = input("Enter the full path to the input file (.xlsx / .xls / .csv): ").strip()

    header_input = input(f"Enter the Excel row number that contains column headers [default: {DEFAULT_HEADER_ROW}]: ").strip()
    try:
        header_row_one_based = int(header_input) if header_input else DEFAULT_HEADER_ROW
    except ValueError:
        header_row_one_based = DEFAULT_HEADER_ROW

    df = read_input_file(input_path, header_row_one_based)

    print("\n--- Detected input columns ---")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i}. {col!r}")

    dept_col = find_column(df, ["Department", "Dept", "Department Name"])
    course_name_col = find_column(df, [
        "Course Name*(Subject Name)",
        "Course Name*",
        "Course Name",
        "Subject Name",
        "Course Title",
    ])
    course_code_col = find_column(df, [
        "Course Code*( Course code needs to be unique)",
        "Course Code*(Course code needs to be unique)",
        "Course Code*",
        "Course Code",
        "Subject Code",
        "Course ID",
    ])
    description_col = find_column(df, [
        "Description*(Description)",
        "Description*",
        "Description",
        "Course Description",
    ])

    print("\n--- Matched columns ---")
    print(f"  Department    : {dept_col!r}")
    print(f"  Course Name   : {course_name_col!r}")
    print(f"  Course Code   : {course_code_col!r}")
    print(f"  Description   : {description_col!r} (falls back to Course Name if not found)")

    print("\n--- First 3 input rows ---")
    print(df.head(3).to_string(index=False))

    print("\n--- Sample values from matched columns (first row) ---")
    if len(df) > 0:
        first = df.iloc[0]
        print(f"  Course Name   : {first.get(course_name_col, 'N/A')!r}" if course_name_col else "  Course Name   : <column not matched>")
        print(f"  Course Code   : {first.get(course_code_col, 'N/A')!r}" if course_code_col else "  Course Code   : <column not matched>")
        print(f"  Description   : {first.get(description_col, 'N/A')!r}" if description_col else "  Description   : <column not matched, will use Course Name>")

    if not dept_col:
        raise ValueError("Required column 'Department' not found in the input file.")
    if not course_name_col:
        print("\nWARNING: Could not detect a 'Course Name' column.")
    if not course_code_col:
        print("\nWARNING: Could not detect a 'Course Code' column.")

    component_groups = locate_component_groups(df)
    if not component_groups:
        raise ValueError(
            "No component columns (e.g. 'Component 1', 'Component 2') were found in the input file."
        )

    output_rows, _ = build_output_rows(df, component_groups)

    # Build final ordered column list using the fixed component order
    final_columns = OUTPUT_BASE_COLUMNS.copy()
    for comp_name in FIXED_COMPONENTS:
        final_columns.append(f"{comp_name} Credits")
        final_columns.append(f"{comp_name} Hours")
    final_columns.extend(TRAILING_COLUMNS)

    output_df = pd.DataFrame(output_rows, columns=final_columns)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Group by department and write one file per department
    for department, group in df.groupby(dept_col, sort=False):
        dept_name = str(department).strip()
        if not dept_name or dept_name.lower() == "nan":
            continue

        dept_df = output_df.loc[group.index].copy()
        dept_df = dept_df[final_columns]  # ensure column order

        safe_name = sanitize_filename(dept_name)
        output_file = OUTPUT_DIR / f"{safe_name}{OUTPUT_FILE_EXTENSION}"

        # Remove previous versions of this department's file (including old _1, _2, etc.)
        for existing in OUTPUT_DIR.glob(f"{safe_name}*"):
            if existing.suffix.lower() == OUTPUT_FILE_EXTENSION:
                try:
                    existing.unlink()
                except PermissionError:
                    print(f"\nERROR: Could not replace {existing} because it is open in another program.")
                    print("Please close all output Excel files and run the script again.\n")
                    raise

        dept_df.to_excel(output_file, index=False)
        print(f"Written: {output_file} ({len(dept_df)} rows)")

    print(f"\nAll department files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
