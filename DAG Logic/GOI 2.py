"""
Monthly licence / login report by department and user type, saved as one Excel file:

  summary    : one row per month + department (plus department = ALL for the whole university).
               For each user type: licensed, unique users logged in that month, never logged in
               (since login data starts), dormant (no login
               in the last 30 days), app / browser share of logins; plus the last login (any type).
  user_level : one row per user: department, last login, login counts (7 / 30 / 90 days) and
               primary device, measured back from the last day of login data.

Sources
  license_user_summary_report : daily licensed count per user_type / department_id
  login_report                : one row per login (ukid, timestamp, device_type)
  user_details_report         : ukid -> user_type, department (login_report has neither)
"""
from pathlib import Path
import pandas as pd

LICENCES = r"C:\Users\suraj\Downloads\license_user_summary_report_ttd.csv"
LOGINS = r"C:\Users\suraj\Downloads\login_report_ttd.csv"
USERS = r"C:\Users\suraj\Downloads\user_details_report_ttd.csv"
OUTPUT = Path(r"C:\Users\suraj\OneDrive\Desktop\final dataset summary_ttd.xlsx")
FMT = "%d %b, %Y %H:%M:%S"
TYPE_ORDER = ["student", "faculty", "staff", "parent", "prospective_student", "unmapped"]  # rest A-Z
IGNORE_TYPES = ["collpoll-admin"]  # left out of every number and the per-user dataset
KEYS = ["tenant_id", "department_id", "user_type"]
COUNTS = ["licensed", "unique_logged_in", "never_logged_in", "dormant_30d"]
OTHERS = ["app_share_pct", "browser_share_pct"]


def dept_key(s: pd.Series) -> pd.Series:
    """department_id as a string key ('90', not '90.0'); missing -> 'unmapped'."""
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str).replace("<NA>", "unmapped")


def add_all_department(df: pd.DataFrame) -> pd.DataFrame:
    """Copy every row under department 'ALL' so university-wide figures use the same logic."""
    return pd.concat([df, df.assign(department_id="ALL")], ignore_index=True)


def load_users() -> pd.DataFrame:
    um = pd.read_csv(USERS, low_memory=False)[["ukid", "user_type", "tenant_id", "department_id", "department_name"]]
    um = um.drop_duplicates("ukid")
    um["department_id"] = dept_key(um["department_id"])
    return um


# ---------- 1. Licensed per month: count on the last available date in the month ----------
def licences() -> pd.Series:
    s = pd.read_csv(LICENCES)
    s["date"] = pd.to_datetime(s["logged_date"], format=FMT)
    s["month"] = s["date"].dt.to_period("M")
    s["department_id"] = dept_key(s["department_id"])
    daily = s.groupby(KEYS + ["month", "date"], as_index=False)["count"].sum()
    last = daily[daily["date"] == daily.groupby(KEYS + ["month"])["date"].transform("max")]
    return add_all_department(last).groupby(KEYS + ["month"])["count"].sum().rename("licensed")


# ---------- 2. Login metrics per month ----------
def logins(users: pd.DataFrame) -> pd.DataFrame:
    lg = pd.read_csv(LOGINS)
    lg = lg[lg["success"].str.strip().str.lower().eq("yes")]
    lg["ts"] = pd.to_datetime(lg["timestamp"], format=FMT)
    lg["day"] = lg["ts"].dt.normalize()
    lg["month"] = lg["day"].dt.to_period("M")
    lg["is_app"] = lg["device_type"].str.strip().str.upper().eq("APP")
    lg = lg.merge(users[["ukid", "user_type", "department_id"]], on="ukid", how="left")
    lg["user_type"] = lg["user_type"].fillna("unmapped").str.lower()
    lg["department_id"] = lg["department_id"].fillna("unmapped")
    return lg[~lg["user_type"].isin(IGNORE_TYPES)]


def login_metrics(lg: pd.DataFrame, months) -> pd.DataFrame:
    last_day = lg["day"].max()
    out = []
    for m in months:
        end = min(m.to_timestamp(how="end").normalize(), last_day)  # current month: last data day
        upto = lg[lg["month"] <= m].groupby(KEYS)
        recent = lg[(lg["day"] > end - pd.Timedelta(days=30)) & (lg["day"] <= end)]
        this_month = lg[lg["month"] == m]
        out.append(pd.DataFrame({
            "unique_logged_in": this_month.groupby(KEYS)["ukid"].nunique(),  # logged in this month
            "ever_logged_in": upto["ukid"].nunique(),        # logged in at least once so far
            "active_30d": recent.groupby(KEYS)["ukid"].nunique(),
            "last_login": upto["ts"].max(),                   # may be from an earlier month
            "app_share_pct": this_month.groupby(KEYS)["is_app"].mean().mul(100).round(1),
        }).assign(month=m))
    df = pd.concat(out).set_index("month", append=True)
    df["browser_share_pct"] = (100 - df["app_share_pct"]).round(1)
    return df


# ---------- 3. Summary: one row per month + department, columns grouped by user type ----------
def summary(users: pd.DataFrame, lg: pd.DataFrame) -> pd.DataFrame:
    lic = licences()
    lg = add_all_department(lg)
    months = sorted(set(lic.index.get_level_values("month")) & set(lg["month"]))  # in both sources

    df = pd.concat([lic, login_metrics(lg, months)], axis=1)
    df = df[df.index.get_level_values("month").isin(months)]
    filled = ["unique_logged_in", "ever_logged_in", "active_30d"]
    df[filled] = df[filled].fillna(0)
    # ever_logged_in (cumulative) is only used here, not shown
    df["never_logged_in"] = (df["licensed"] - df["ever_logged_in"]).clip(lower=0)
    df["dormant_30d"] = (df["licensed"] - df["active_30d"]).clip(lower=0)  # includes never logged in

    wide = df[COUNTS + OTHERS].unstack("user_type")
    # count columns only for types that have them (e.g. no licences for parents); missing -> 0
    counts = wide[COUNTS].dropna(axis=1, how="all").fillna(0)
    wide = pd.concat([counts, wide[OTHERS]], axis=1)
    types = TYPE_ORDER + sorted(set(wide.columns.get_level_values(1)) - set(TYPE_ORDER))
    wide = wide[[(m, t) for t in types for m in COUNTS + OTHERS if (m, t) in wide.columns]]
    wide.columns = [f"{t}_{m}" for m, t in wide.columns]
    # one last login per row: latest across all user types
    wide["last_login"] = df["last_login"].unstack("user_type").max(axis=1)
    wide = wide.reset_index()

    # department names from the user list, per tenant (ids repeat across tenants);
    # unknown ids keep their id
    names = (users.dropna(subset=["department_name"])
                  .drop_duplicates(["tenant_id", "department_id"])
                  .set_index(["tenant_id", "department_id"])["department_name"])
    name = pd.Series([names.get(k) for k in zip(wide["tenant_id"], wide["department_id"])],
                     index=wide.index)
    special = wide["department_id"].isin(["ALL", "unmapped"])
    name = name.where(~special, wide["department_id"]).fillna("Department " + wide["department_id"])
    wide.insert(2, "department_name", name)

    # rows: by month, then department = ALL first, A-Z, unmapped last
    wide["_dept_order"] = wide["department_name"].map(
        lambda n: (n != "ALL", n == "unmapped", n))
    wide = wide.sort_values(["tenant_id", "month", "_dept_order"], kind="stable")
    wide.insert(1, "month_year", wide.pop("month").dt.strftime("%b %Y"))
    return wide.drop(columns="_dept_order")


# ---------- 4. Per-user dataset: every user in the user list ----------
def user_level(users: pd.DataFrame, lg: pd.DataFrame) -> pd.DataFrame:
    ref = lg["day"].max()  # measure recency back from the last day of login data
    df = users[~users["user_type"].isin(IGNORE_TYPES)].rename(columns={"tenant_id": "college_id"})
    by_user = lg.groupby("ukid")

    last = df["ukid"].map(by_user["ts"].max())
    days = (ref - last.dt.normalize()).dt.days
    within_90 = days <= 90
    df["last_login_date_in_last_90_days"] = last.where(within_90)
    df["days_since_last_login"] = days.where(within_90)
    for n in (7, 30, 90):
        recent = lg[lg["day"] >= ref - pd.Timedelta(days=n)].groupby("ukid").size()
        df[f"login_count_{n}d"] = df["ukid"].map(recent).fillna(0).astype(int)
    device = by_user["device_type"].agg(lambda x: x.mode().iloc[0] if x.notna().any() else None)
    df["primary_device"] = df["ukid"].map(device).where(within_90)  # most used device

    return df[["ukid", "user_type", "college_id", "department_id", "department_name",
               "last_login_date_in_last_90_days", "days_since_last_login", "login_count_7d",
               "login_count_30d", "login_count_90d", "primary_device"]]


if __name__ == "__main__":
    users = load_users()
    lg = logins(users)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUTPUT) as xw:
        summary(users, lg).to_excel(xw, sheet_name="summary", index=False)
        user_level(users, lg).to_excel(xw, sheet_name="user_level", index=False)
    print(f"Saved: {OUTPUT}")
