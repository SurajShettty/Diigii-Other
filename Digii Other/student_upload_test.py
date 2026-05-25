import pandas as pd
import re

def validate_and_save(input_csv, output_excel):
    df = pd.read_csv(input_csv)

    # Fill blank columns with ''
    df.fillna('', inplace=True)

    # Track duplicates
    reg_id_counts = df['Registration Id'].duplicated(keep=False)
    email_counts = df['Email Id'].duplicated(keep=False)

    messages = []

    for index, row in df.iterrows():
        row_msgs = []

        # Check for mandatory fields (except Phone Number)
        for col in df.columns:
            if col not in ['Phone Number','Intake'] and not row[col]:
                row_msgs.append(f"{col} is mandatory")

        # Registration Id duplication
        if row['Registration Id'] and reg_id_counts.iloc[index]:
            row_msgs.append("Duplicate Registration Id")

        # Email Id duplication
        if row['Email Id'] and email_counts.iloc[index]:
            row_msgs.append("Duplicate Email Id")

        # Email format
        if row['Email Id'] and not re.match(r"[^@]+@[^@]+\.[^@]+", row['Email Id']):
            row_msgs.append("Invalid Email Format")

       # Clean and validate Phone Number
        phone = row.get('Phone Number')

        # If phone number is not empty
        if pd.notna(phone) and str(phone).strip():
            # Convert to string, remove .0 if float
            phone_str = str(phone).strip()

            # Remove decimal part if it's .0 (common in Excel/CSV)
            if phone_str.endswith('.0'):
                phone_str = phone_str[:-2]

            # Extract digits only
            phone_digits = ''.join(filter(str.isdigit, phone_str))

            if len(phone_digits) != 10:
                row_msgs.append("Invalid Phone Number")
            else:
                df.at[index, 'Phone Number'] = phone_digits  # optional: clean in output

        # Intake Name check
        year_raw = row.get('Year of Joining')
        programme = row.get('Programme')
        intake_name = row.get('Intake')

        # Validate and convert year
        if pd.notnull(year_raw):
            try:
                year = int(float(year_raw))  # Handles '2020.0' or '2020'
            except (ValueError, TypeError):
                year = None
        else:
            year = None

        # Build expected intake string only if year and programme are valid
        expected_intake = f"{programme}-{year}-intake"
        if intake_name != expected_intake:
            row_msgs.append("Invalid Intake Name")
        

        # Name check
        name_words = row['Name'].strip().split()
        if len(name_words) == 1:
            df.at[index, 'Name'] = f"{row['Name']} ."
            row_msgs.append("Name had only 1 word; formatted")

        # Gender validation
        gender = row['Gender(Male/Female/Other)'].strip().capitalize()
        if gender == 'M':
            gender = 'Male'
            df.at[index, 'Gender(Male/Female/Other)'] = gender
        elif gender == 'F':
            gender = 'Female'
            df.at[index, 'Gender(Male/Female/Other)'] = gender
        elif gender not in ['Male', 'Female', 'Other', '']:
            row_msgs.append("Invalid Gender")

        # Accommodation Type check
        acc_type = row['Accommodation Type(DAY_SCHOLAR/HOSTELLER)'].strip().upper()
        if acc_type not in ['DAY_SCHOLAR', 'HOSTELLER', '']:
            row_msgs.append("Invalid Accommodation Type")

        # Final message
        if not row_msgs:
            messages.append("Can be created")
        else:
            messages.append(", ".join(row_msgs))

    df['Message'] = messages

    # Save to Excel
    df.to_excel(output_excel, index=False)
    print(f"Processed file saved as '{output_excel}'")

# Example usage
input_csv = "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\student_creation front end.csv"
output_excel = "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\validated_output.xlsx"
validate_and_save(input_csv, output_excel)
