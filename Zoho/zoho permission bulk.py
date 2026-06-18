import re
import sys
import pandas as pd
import requests
from collections import defaultdict

# === Utility ===
def canonical(name: str) -> str:
    """Normalize column names (lowercase, no spaces/punctuation)."""
    return re.sub(r'\W+', '', name.strip().lower())

def find_col(cols, key):
    """Find column matching key (exact or substring)."""
    canon_key = canonical(key)
    if canon_key in cols:
        return canon_key
    for c in cols:
        if canon_key in c:
            return c
    return None

# === Step 1: Read input files ===
df1 = pd.read_excel(r"C:\Users\suraj\OneDrive\Desktop\data111.xlsx")
df2 = pd.read_excel(r"C:\Users\suraj\OneDrive\Desktop\data222.xlsx")

# === Step 2: Normalize column names ===
df1.columns = [canonical(c) for c in df1.columns]
df2.columns = [canonical(c) for c in df2.columns]

all_cols = set(df1.columns).union(df2.columns)

# === Step 3: Detect required columns ===
required_fields = ["ukid", "id", "module", "report_name", "tenant_id"]
col_map = {f: find_col(all_cols, f) for f in required_fields}

missing = [f for f, c in col_map.items() if f != "id" and not c]
if missing:
    print(f"❌ Missing required columns after normalization: {missing}")
    print(f"Available columns: {sorted(all_cols)}")
    sys.exit(1)

tenant_col = col_map["tenant_id"]

# === Step 4: Merge ===
merged = pd.merge(df1, df2, on=tenant_col, how='inner')

# === Step 5: Pick correct ukid column after merge (handle suffixes) ===
ukid_col = find_col(merged.columns, "ukid")
if not ukid_col:
    print("⚠️  Warning: ukid column not found after merge.")
else:
    col_map["ukid"] = ukid_col

# === Step 6: Select and rename final columns ===
final_cols = {v: k for k, v in col_map.items() if v and v in merged.columns}
final_df = merged[list(final_cols.keys())].rename(columns=final_cols)

# === Step 7: Export ===
final_df.to_excel(r"C:\Users\suraj\OneDrive\Desktop\final.xlsx", index=False)
print("✅ Report generated successfully: final.xlsx")


# ==========================
# 🚀 Step 8: API Integration
# ==========================

# --- Group by report_id ---
grouped = defaultdict(list)
for _, row in final_df.iterrows():
    grouped[row["id"]].append({
        "ukid": int(row["ukid"]),
        "analyticsTenantModuleReportId": int(row["id"]),
        "module": None  # can be replaced with row["module"] if needed
    })

# --- API details ---
url = "https://bi.digiicampus.com/api/analytics/permission"  # ⬅️ Replace with your API URL
headers = {
    "Auth-Token": "eyJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiZGlyIn0..Fw5hx_iGxusT_Dat.jF9JE0pYJOXrFDK4Sivjgbp3tfg7LBUNrkMFRI5aIPWAanrbdClyY24k15zZDIDKahkAM9k9IrL-OzEiO2wojQqRKIjmL2l_us_Lk0QamvQLabOuwdaB-pbcLV0mbGwct1YeulcWYq_uR1P6J4J3ObbTYWHwNOcnHwX6C55MeN8UGEfeFzCdggy-59p5CKud5c1ufVs0l0oyzl4vglNyo1430IS06XlyxZ_rVcJOIHvIT1KA_59YOJbAM4bNdyrsfWhhj0I4lEPzJVR7sR3_4jI9pvzuAiDPBgs8wuUDIL7kA3Len2XPpMfc9aZTdPZi9EjLSisiE0Q1VT95CdmkH6Gcs663ButCUKIS6PLEmn54xTJJbEulxoOfdESFa0icUbJgenXOSgr_181HDbEn5mCbtiW8dEYs6uIqqNIbVggIrDvHVZYIZBGbSApx9Lta0pnQdaer5qFNCGIqARpdI9HFdJm9AVC-YoSIS3BqY-nVa6SSUkhapweVfwPYh7AKNL3oOskLz-NKAYJ03oKX4OJD242SOIayJ3NMxHohTqx56QqbxauWvM1q8OEb6RsnBnf_CNsdSfZKQJmSlg3lIJcFR-yJ1nZ9uwV0ykkO099FOAJUczG4qzjGDgeC7Bl7hcN0uiho522AoxQODpgsXFeV433C70U876n8GrOAhAW7xw01kITag-ADwtrIYwwFJpTvGDzqibvfN7_50VxbBVjEOs0gAAj0v4BM3h9I75hVu-2eMxL2BJj3dGy65KQSofdZCQ806JEVHhZXcauOQmGXqnTuUu0l3VQwdG4x6SuRQwTgHPqXLgrU-MfiQEzzqHCFbM9R6o3NI_3dervx4RBWP3Hc205YnR9oReqSrV-7u8D5Ln5z_nt9AQfrQnw5kdJot14spgOgNrnZ-SUmMhAndU5791w3D1E9lAHbxdyvn4eiDnBI4hbU5sOjji9nyx5nMemStEy4_UAxMaSO5SI0yNxt_DYLzL3azGoDg_JFg6exIYx6AnDW206A5jV-aBPOU2DeECiwxbiIghoi5f6UoWx8pX_DzSOTERCih0Gc1KqSyOnWaUvQU5cEg8jTb2bJAQNrA_HmvEUgBNQy5sbyO06rRJtFflUeYJYB9nffxyEH2CQJcnsN3hIYWo5tMtv256fQnlGo2-bwCCelYExCwQFAUbcK7oBMEAZPRYPRmB3TzXmowqWBCe8GsaKuVV8gLR9xgPI8URjNmJE7ZGmTd-7bwiuWE0Wce81F-tj62VLLhBSOPLianPgSK5-ZRuwpJmLkDYrguckwkzQjtZ9QvV-x_SiZCr2Vxjz1mgkloIaT8v6KvVi9-nFymEPMqe-9zpI4OE0yGVzljKINJTZCiRr79xAzyJknqFTmnE5UN76tIsAz1Rk7RNJYoq5xRuF38FeMf7TZIxnt_SvckQYaW44WbdLjNfqysbkWT1gRywp2fAW5IB5HXwONTE8LMW5K2SOv193yEXZDZ1doXchGL1aHHPu_Y0Fi29KEHq24YnFomKVJhBMMcGVMV1JJnMIPTxRWGukmc5rwLk1c5sT1Jwgw7pfQW_Z650qoXXAPt4Os-UxeVkju8UybqBsW6sf6qGo6o_Bkc_znpYWbBqcAtrQa4HWUtfqIU3plYq_uBnpMHCd-tHzdj-KKctHRuS_OeiyiEDouVg0n4IT_MrYxd5qHNtrG5z6EvCiHH5qQmBSM3TxQMcQgB5Q4SjHUBQ2bhyCIFW0mHXagBeFEMvpG5Wi3f0-DcUk2VM6FDeRQwz1EyKCv_uaCf1znkJP_mndDQ7YGJvn958KzCP_F_uzHHiKpl12ViF6RzsNU4dBDmBO6BtAyED8waOaJ22Oqz9N3A3D-ttrPPqe2OFwlsi7ylTP_I50wuqfCw9ZXe3I1bTTXpy0dRFLoTk3mU0HCPr2QtEJ_9Oh5Aw0uekOc_Ecz_Al3M1vRE7mLgCMmq_9TWbn8cw4FIyXpePeX3IY2O74in8NwtROmSQ60g3n0f5rytd4C5HAINOLfcWzC8fov5h0uxmoirYIN_aobLVdZ-n3Nvzuln16pV-VZca_ZiJ6GsO75WX5Zh8I58fNggrwCy8RE2sLxyTACjiTa4kLHQQJQIeWvD2wZ680N0N__FMLuzzNMkDWTpcf8GBANJ5dHqZta10bn3CGJtlwKPGoMi1jtKvggsWMVITDS3IaESKOi6LZBzUU8ESITbWOvQzdewjhvXBeSDH1YaX2rJGo1b37NJXMZ9mqyFRgquvBN0z2VC7z7ywkLujqJE9twhABG3GVm3t9o9Cksn3GWUPHeyZ3VLQtXA54n.d6ITicSEArlcsX9gKRkToA",            # ⬅️ Replace with real token
    "Content-Type": "application/json"
}

# --- Send PUT request for each report_id ---
for report_id, users in grouped.items():
    payload = {"userPermissions": users}
    response = requests.put(url, json=payload, headers=headers)
    if response.ok:
        print(f"✅ Successfully updated report_id {report_id}")
    else:
        print(f"❌ Failed for {report_id}: {response.status_code} - {response.text}")