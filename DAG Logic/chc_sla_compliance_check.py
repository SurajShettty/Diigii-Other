import pandas as pd

CHC_REPORT_FILE = r"C:\Users\suraj\OneDrive\Desktop\ISBHYD chc reportt.csv"
SLA_FILE = r"C:\Users\suraj\OneDrive\Desktop\ISBHYD elemenst.csv"
OUTPUT_FILE = r"C:\Users\suraj\OneDrive\Desktop\ISBHYD chc report with SLA status.csv"

chc_report = pd.read_csv(CHC_REPORT_FILE)
sla = pd.read_csv(SLA_FILE)

# Normalize join keys for a case/whitespace-insensitive match
chc_report["_service_key"] = chc_report["service"].astype(str).str.strip().str.lower()
chc_report["_complaint_key"] = chc_report["nature"].astype(str).str.strip().str.lower()

sla["_service_key"] = sla["Service"].astype(str).str.strip().str.lower()
sla["_complaint_key"] = sla["Complaint"].astype(str).str.strip().str.lower()

chc_report = chc_report.merge(
    sla[["_service_key", "_complaint_key", "SLA (in minutes)"]],
    on=["_service_key", "_complaint_key"],
    how="left"
)

is_closed = chc_report["status"].astype(str).str.strip().str.lower() == "closed"

chc_report["Followed"] = ""
chc_report.loc[is_closed, "Followed"] = (
    chc_report.loc[is_closed, "tat_minutes"] <= chc_report.loc[is_closed, "SLA (in minutes)"]
).map({True: "Followed", False: "Not Followed"})

# Closed requests with no matching SLA entry can't be evaluated
no_sla_match = is_closed & chc_report["SLA (in minutes)"].isna()
chc_report.loc[no_sla_match, "Followed"] = "SLA not found"

chc_report = chc_report.drop(columns=["_service_key", "_complaint_key", "SLA (in minutes)"])

chc_report.to_csv(OUTPUT_FILE, index=False)

print(f"Closed requests evaluated: {is_closed.sum()}")
print(chc_report.loc[is_closed, "Followed"].value_counts())
print(f"Saved to: {OUTPUT_FILE}")
