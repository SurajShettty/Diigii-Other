import os
import pandas as pd

# 👉 Input and Output folders
input_folder = r"C:\Users\suraj\OneDrive\Desktop\MABFSI inactive attendace"
output_folder = r"C:\Users\suraj\OneDrive\Desktop\output_folder"

# Create output folder if not exists
os.makedirs(output_folder, exist_ok=True)

# Dictionary to store combined data for each term
term_data = {}

# Loop through all CSV files
for file in os.listdir(input_folder):
    if file.endswith(".csv"):
        file_path = os.path.join(input_folder, file)
        print(f"Processing: {file}")

        try:
            df = pd.read_csv(file_path)

            # Check if 'term' column exists
            if 'term_name' not in df.columns:
                print(f"⚠️ Skipping {file} (no 'term' column)")
                continue

            # Group by term
            for term, group in df.groupby('term_name'):
                if term not in term_data:
                    term_data[term] = []

                term_data[term].append(group)

        except Exception as e:
            print(f"❌ Error in {file}: {e}")
            break  # stop execution if any file fails (as you prefer)

# Save combined data for each term
for term, dataframes in term_data.items():
    final_df = pd.concat(dataframes, ignore_index=True)

    # Clean term name for filename
    safe_term = str(term).replace(" ", "_").replace("/", "_")

    output_file = os.path.join(output_folder, f"{safe_term}.csv")
    final_df.to_csv(output_file, index=False)

    print(f"✅ Saved: {output_file}")

print("🎯 Done!")