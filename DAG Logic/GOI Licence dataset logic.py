"""
Builds final_dataset_report from:
  - licence_users_ukid_report  (identity master: user_type, college_id)
  - inactive_user_report       (base population + canonical last_login_timestamp)
  - login_report               (event log -> rolling counts + device mix)

Output columns:
  ukid, user_type, college_id, last_login_date_in_last_90_days,
  days_since_last_login, login_count_7d, login_count_30d, login_count_90d,
  primary_device
"""
import pandas as pd

LOGIN_REPORT_PATH = "C:\\Users\\suraj\\Downloads\\login_report (1).xlsx"
INACTIVE_REPORT_PATH = "C:\\Users\\suraj\\Downloads\\inactive_user_report.xlsx"
UKID_SNAPSHOT_PATH = "C:\\Users\\suraj\\OneDrive\\Desktop\\licence_users_ukid_report.csv"
OUTPUT_PATH = "C:\\Users\\suraj\\OneDrive\\Desktop\\final dataset report.csv"

REF_DATE = pd.Timestamp.today().normalize()  # run date; swap for a fixed date if backfilling


def build(login_path=LOGIN_REPORT_PATH, inactive_path=INACTIVE_REPORT_PATH,
          ukid_snapshot_path=UKID_SNAPSHOT_PATH, ref_date=REF_DATE):
    login = pd.read_excel(login_path)
    inactive = pd.read_excel(inactive_path)
    ukid_snap = pd.read_csv(ukid_snapshot_path)

    # ---- 1. Identity master: latest snapshot per ukid -> user_type, college_id ----
    ukid_snap["logged_date"] = pd.to_datetime(ukid_snap["logged_date"], format="%d-%m-%Y")
    latest_attrs = (
        ukid_snap.sort_values("logged_date")
        .groupby("user_ukid").tail(1)
        .rename(columns={"user_ukid": "ukid", "tenant_id": "college_id"})
        [["ukid", "user_type", "college_id"]]
    )

    # ---- 2. Base population + canonical last login (inactive_user_report) ----
    base = (
        inactive[["ukid", "tenant_id", "last_login_timestamp"]]
        .drop_duplicates(subset="ukid")
        .rename(columns={"tenant_id": "college_id"})
    )
    base = base.merge(latest_attrs[["ukid", "user_type"]], on="ukid", how="left")

    # ---- 3. 90-day recency gate ----
    days_since = (ref_date - base["last_login_timestamp"].dt.normalize()).dt.days
    within_90 = days_since <= 90
    base["days_since_last_login"] = days_since.where(within_90)
    base["last_login_date_in_last_90_days"] = base["last_login_timestamp"].where(within_90)

    # ---- 4. Rolling login counts + primary device (login_report event log) ----
    login["date"] = login["timestamp"].dt.normalize()

    def counts_for(days):
        cutoff = ref_date - pd.Timedelta(days=days)
        return login[login["date"] >= cutoff].groupby("ukid").size()

    c7, c30, c90 = counts_for(7), counts_for(30), counts_for(90)
    device_mode = login.groupby("ukid")["device_type"].agg(
        lambda x: x.mode().iloc[0] if not x.mode().empty else None
    )

    base["login_count_7d"] = base["ukid"].map(c7).fillna(0).astype(int)
    base["login_count_30d"] = base["ukid"].map(c30).fillna(0).astype(int)
    base["login_count_90d"] = base["ukid"].map(c90).fillna(0).astype(int)
    base["primary_device"] = base["ukid"].map(device_mode).where(within_90)

    cols = ["ukid", "user_type", "college_id", "last_login_date_in_last_90_days",
            "days_since_last_login", "login_count_7d", "login_count_30d",
            "login_count_90d", "primary_device"]
    return base[cols]


if __name__ == "__main__":
    result = build()
    result.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(result)} rows to {OUTPUT_PATH}")