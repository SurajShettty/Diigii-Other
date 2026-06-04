import pandas as pd
import time
from datetime import datetime
import os
import io
import xlsxwriter

# --- START TIMER ---
start_time = time.time()

# === CONFIG ===
exotel_folder = r"C:\Users\suraj\Downloads\202664112222_2026_06_04_11_23_32_2332"
user_details_file = r"C:\Users\suraj\Downloads\Diigii-Other\Exotel_NexG\user_details_for_nexG 04-06-2026.csv"
sms_templates_file = r"C:\Users\suraj\Downloads\Diigii-Other\Exotel_NexG\SMS Templates Active - Sheet1.csv"
output_file = fr"C:\Users\suraj\OneDrive\Desktop\nexG_sms_report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

# === STEP 1: READ & COMBINE EXOTEL CSV FILES ===
exotel_dataframes = []

for file in os.listdir(exotel_folder):
    if not file.lower().endswith('.csv'):
        continue

    path = os.path.join(exotel_folder, file)
    try:
        # Read UTF-16 Little Endian tab-separated
        with open(path, "rb") as f:
            raw = f.read()
        decoded = raw.decode("utf-16-le")

        df = pd.read_csv(io.StringIO(decoded), sep='\t', dtype=str)

        # 🧹 Clean column names (remove quotes/spaces)
        # After reading CSV into df
        df.columns = df.columns.str.replace('"', '').str.strip().str.upper()

        if 'TEMPLATE_ID' in df.columns:
            df['TEMPLATE_ID'] = df['TEMPLATE_ID'].astype(str).str.strip().str.upper()


        exotel_dataframes.append(df)
        print(f"✅ Loaded {file} ({len(df)} rows, {len(df.columns)} cols) — UTF-16-LE tab-separated")

    except Exception as e:
        print(f"⚠️ Skipped {file}: {e}")

if not exotel_dataframes:
    raise ValueError("❌ No valid CSV files could be read successfully!")

# Combine all CSVs
exotel_log = pd.concat(exotel_dataframes, ignore_index=True)

# Print columns once for sanity check
print("\n📄 Columns found in Exotel data:")
print(exotel_log.columns.tolist())

# === STEP 2: READ USER DETAILS FILE ===
user_details = pd.read_csv(
    user_details_file,
    encoding="latin1",
    dtype=str,
    engine="python"
)
user_details.columns = user_details.columns.str.strip().str.lower()

# === STEP 3: CLEAN PHONE NUMBERS ===
user_details = user_details.rename(columns={"phone": "userPhone"})
exotel_log.columns = exotel_log.columns.str.strip().str.upper()

# Try to find the column that holds phone numbers in Exotel log
possible_phone_cols = [c for c in exotel_log.columns if 'CONTACT' in c.upper() or 'PHONE' in c.upper()]
if not possible_phone_cols:
    raise KeyError("❌ Could not find any phone/contact column in Exotel log.")
exotel_phone_col = possible_phone_cols[0]

exotel_log = exotel_log.rename(columns={exotel_phone_col: "nexgPhone"})
exotel_log['nexgPhone'] = exotel_log['nexgPhone'].astype(str).str.replace(r'\D', '', regex=True).str[-10:]
user_details['userPhone'] = user_details['userPhone'].astype(str).str.replace(r'\D', '', regex=True).str[-10:]

# === STEP 4: MERGE ===
join = pd.merge(exotel_log, user_details, how='left',
                left_on='nexgPhone', right_on='userPhone')

# Add tenant-related columns safely
for col in ['tenant_name', 'is_tenant_active', 'is_exotel_used']:
    if col not in join.columns:
        join[col] = 'N/A'

join['tenant_name'] = join['tenant_name'].fillna('Unable to Find')
join = join.drop_duplicates()

# === STEP 5: HANDLE DUPLICATES ===
if 'TRANSACTION_ID' in join.columns:
    counts = join['TRANSACTION_ID'].value_counts()

    # Find duplicates
    duplicate_ids = counts[counts > 1].index
    duplicates = join[join['TRANSACTION_ID'].isin(duplicate_ids)].copy()

    # Mark duplicates in main join
    join['is_duplicate'] = join['TRANSACTION_ID'].isin(duplicate_ids)
    print(f"🧭 Found {len(duplicates)} duplicate records.")
else:
    duplicates = pd.DataFrame()
    join['is_duplicate'] = False
    print("⚠️ TRANSACTION_ID column not found, skipping duplicate filtering.")

# === STEP 6: READ SMS TEMPLATE FILE ===
sms_templates = pd.read_csv(
    sms_templates_file,
    encoding="latin1",
    dtype=str,
    engine="python"
)
sms_templates.columns = sms_templates.columns.str.strip().str.lower()

# Identify correct column name for chargeable flag
flag_col_candidates = [c for c in sms_templates.columns if "charge" in c]
if not flag_col_candidates:
    raise KeyError("❌ No column indicating 'Chargeable / Non Chargeable' found in template file.")
flag_col = flag_col_candidates[0]


# Normalize template_id and chargeability flags
sms_templates['template_id'] = sms_templates['template_id'].astype(str).str.strip().str.upper()
sms_templates[flag_col] = sms_templates[flag_col].astype(str).str.lower().str.strip()


chargable = sms_templates[sms_templates[flag_col].str.contains('chargable', na=False)]
non_chargable = sms_templates[sms_templates[flag_col].str.contains('non', na=False)]

chargable_list = chargable['template_id'].dropna().tolist()
non_chargable_list = non_chargable['template_id'].dropna().tolist()

print(f"📊 Templates loaded: {len(sms_templates)} | Chargeable: {len(chargable_list)} | Non-chargeable: {len(non_chargable_list)}")

# === STEP 7: FILTER CHARGABLE (only if column exists) ===
template_col = None
for c in join.columns:
    if 'TEMPLATE' in c.upper():
        template_col = c
        break

if template_col:
    join[template_col] = join[template_col].astype(str).str.strip().str.upper()
    exotel_log[template_col] = exotel_log[template_col].astype(str).str.strip().str.upper()

    # 🟩 Non-chargeable data for separate tab
    non_chargeable_df = join[join[template_col].isin(non_chargable_list)].copy()
    print(f"🟩 Found {len(non_chargeable_df)} non-chargeable messages")

    # 🟨 Chargeable data for tenant tabs
    chargeable_df = join[join[template_col].isin(chargable_list)].copy()
    print(f"🟨 Found {len(chargeable_df)} chargeable messages for tenant sheets")

    # Keep 'join' as chargeable only for tenant tab writing
    join = chargeable_df
else:
    non_chargeable_df = pd.DataFrame()
    print("⚠️ TEMPLATE_ID column not found in Exotel log, skipping chargeable filtering.")

print("\n--- 🧩 TEMPLATE ID DEBUG DIAGNOSTIC ---")

# 1️⃣ Normalize both sides strongly
exotel_log['TEMPLATE_ID'] = (
    exotel_log['TEMPLATE_ID']
    .astype(str)
    .str.strip()
    .str.replace('"', '')
    .str.replace(r'\.0$', '', regex=True)
    .str.replace(r'\s+', '', regex=True)
    .str.upper()
)
non_chargable_list = [
    str(x).strip().replace('"', '').replace('.0', '').replace(' ', '').upper()
    for x in non_chargable_list
]

# 2️⃣ Quick sample display
print("➡ nexG unique TEMPLATE_IDs:", exotel_log['TEMPLATE_ID'].unique())
print("➡ Non-chargeable TEMPLATE_IDs (from SMS file):", non_chargable_list[:10])

# 3️⃣ Compare and show mismatched examples
exotel_set = set(exotel_log['TEMPLATE_ID']) 
noncharge_set = set(non_chargable_list)

intersection = exotel_set & noncharge_set
only_in_exotel = list(exotel_set - noncharge_set)[:5]
only_in_templates = list(noncharge_set - exotel_set)[:5]

print(f"\n🔍 Common TEMPLATE_IDs found: {len(intersection)}")
if intersection:
    print("✅ Matches:", list(intersection)[:5])
else:
    print("⚠️ No exact matches found after normalization.")

print("\n🧾 Sample IDs only in Exotel:", only_in_exotel)
print("🧾 Sample IDs only in Non-Chargeable list:", only_in_templates)


# # === STEP 8: BUILD NON-CHARGEABLE LIST ===
# if template_col and template_col in exotel_log.columns:
#     non_chargeable_df = join[join[template_col].isin(non_chargable_list)]
#     print(f"🟩 Found {len(non_chargeable_df)} non-chargeable messages")
# else:
#     non_chargeable_df = pd.DataFrame()
#     print("⚠️ Non-chargeable list skipped (no template column found).")

# === ✅ Convert SPLIT_COUNT column to numeric if it exists ===
for df in [join, duplicates, non_chargeable_df]:
    if not df.empty and 'SPLIT_COUNT' in df.columns:
        df['SPLIT_COUNT'] = pd.to_numeric(df['SPLIT_COUNT'], errors='coerce')


# === STEP 8: WRITE OUTPUT TO EXCEL ===
try:

    # Create writer without options param
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        # Disable URL conversion at workbook level
        workbook = writer.book
        workbook.strings_to_urls = False

        if not duplicates.empty:
            duplicates.to_excel(writer, sheet_name='Duplicates', index=False)

        for each in join['tenant_name'].drop_duplicates():
            sheet_name = each if len(each) <= 30 else each[:30]
            join[join['tenant_name'] == each].to_excel(writer, sheet_name=sheet_name, index=False)

        if not non_chargeable_df.empty:
            non_chargeable_df.to_excel(writer, sheet_name='Non Chargeable List', index=False)


    print(f"\n✅ Excel report generated successfully at:\n{output_file}")

except Exception as e:
    print(f"❌ Error writing Excel file: {e}")

# === STEP 9: EXECUTION TIME ===
elapsed = (time.time() - start_time) / 60
print(f"\n⏱️ Script executed in {elapsed:.2f} minutes.")
