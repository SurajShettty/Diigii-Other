"""
Month-Year report by user type:
    Licensed users | Avg daily logged-in users | Never logged in | Dormant (no login in last 30 days)
    | App / Browser share of logins

Sources
-------
license_user_summary_report.csv : daily licensed count per user_type (by dept / programme)
login_report.csv                : one row per login (ukid = user id, timestamp)
user_master.csv  (OPTIONAL)     : ukid, user_type  -> needed to split logins by user type,
                                  because login_report has no user_type column
"""
from pathlib import Path
import pandas as pd

SUMMARY = "C:\\Users\\suraj\\Downloads\\license_user_summary_report (1).csv"
LOGINS = "C:\\Users\\suraj\\Downloads\\login_report.csv"
USER_MASTER = "C:\\Users\\suraj\\Downloads\\user_details_report.csv"
OUTPUT = Path("C:\\Users\\suraj\\OneDrive\\Desktop\\final dataset report.xlsx")
FMT = "%d %b, %Y %H:%M:%S"
ORDER = ["student", "faculty", "staff", "parent", "prospective_student", "unmapped", "ALL"]


# ---------- 1. Licensed per month (last available date in the month) ----------
def licensed_monthly() -> pd.DataFrame:
    s = pd.read_csv(SUMMARY)
    s["date"] = pd.to_datetime(s["logged_date"], format=FMT)
    daily = s.groupby(["tenant_id", "date", "user_type"], as_index=False)["count"].sum()
    daily["month"] = daily["date"].dt.to_period("M")
    last = daily.groupby(["tenant_id", "month", "user_type"])["date"].transform("max")
    lic = (daily[daily["date"] == last]
           .rename(columns={"count": "licensed"})[["tenant_id", "month", "user_type", "licensed"]])
    total = lic.groupby(["tenant_id", "month"], as_index=False)["licensed"].sum().assign(user_type="ALL")
    return pd.concat([lic, total], ignore_index=True)


# ---------- 2. Logins ----------
def load_logins() -> pd.DataFrame:
    lg = pd.read_csv(LOGINS)
    lg = lg[lg["success"].str.strip().str.lower().eq("yes")]
    lg["day"] = pd.to_datetime(lg["timestamp"], format=FMT).dt.normalize()
    lg["month"] = lg["day"].dt.to_period("M")

    if Path(USER_MASTER).exists():
        um = pd.read_csv(USER_MASTER)[["ukid", "user_type"]].drop_duplicates("ukid")
        lg = lg.merge(um, on="ukid", how="left")
        lg["user_type"] = lg["user_type"].fillna("unmapped").str.lower()
    else:
        lg["user_type"] = "unmapped"
    # duplicate every row as "ALL" so totals come out of the same logic
    return pd.concat([lg, lg.assign(user_type="ALL")], ignore_index=True)


def login_monthly(lg: pd.DataFrame, months) -> pd.DataFrame:
    keys = ["tenant_id", "month", "user_type"]
    daily = lg.drop_duplicates(["tenant_id", "user_type", "ukid", "day"])  # one row per user per day

    # avg logged in = sum of daily distinct users / days in month
    # (days with zero logins count; a partial current month uses days elapsed)
    dau = daily.groupby(keys)["ukid"].size().rename("user_days").reset_index()
    last_day = daily["day"].max()
    dau["days"] = dau["month"].apply(
        lambda m: last_day.day if m == last_day.to_period("M") else m.days_in_month)
    dau["avg_logged_in"] = (dau["user_days"] / dau["days"]).round(1)

    mau = lg.groupby(keys)["ukid"].nunique().rename("unique_logged_in").reset_index()

    # cumulative distinct users who have logged in at least once up to month end
    first = lg.groupby(["tenant_id", "user_type", "ukid"])["month"].min().reset_index()
    ever = pd.concat([
        first[first["month"] <= m].groupby(["tenant_id", "user_type"]).size()
             .rename("ever_logged_in").reset_index().assign(month=m)
        for m in months])

    # distinct users with a login in the 30 days up to month end (or last data day)
    active = []
    for m in months:
        end = min(m.to_timestamp(how="end").normalize(), last_day)
        win = daily[(daily["day"] > end - pd.Timedelta(days=30)) & (daily["day"] <= end)]
        active.append(win.groupby(["tenant_id", "user_type"])["ukid"].nunique()
                         .rename("active_30d").reset_index().assign(month=m))
    active = pd.concat(active)

    # share of login events by device (all logins, not deduped per day)
    is_app = lg["device_type"].str.strip().str.upper().eq("APP")
    dev = (lg.assign(is_app=is_app).groupby(keys)["is_app"].mean().mul(100).round(1)
             .rename("app_share_pct").reset_index())
    dev["browser_share_pct"] = (100 - dev["app_share_pct"]).round(1)

    return (dau[keys + ["avg_logged_in"]]
            .merge(mau, on=keys, how="outer")
            .merge(ever, on=keys, how="outer")
            .merge(active, on=keys, how="outer")
            .merge(dev, on=keys, how="outer"))


# ---------- 3. Combine ----------
def build() -> pd.DataFrame:
    lic = licensed_monthly()
    lg = load_logins()
    first_login_month = lg["month"].min()

    # only months covered by BOTH sources
    months = sorted(set(lic["month"]) & set(lg["month"]))
    lic = lic[lic["month"].isin(months)]
    log = login_monthly(lg, months)
    log = log[log["month"].isin(months)]

    df = lic.merge(log, on=["tenant_id", "month", "user_type"], how="outer")
    counts = ["avg_logged_in", "unique_logged_in", "ever_logged_in", "active_30d"]
    df[counts] = df[counts].fillna(0)
    df["never_logged_in"] = (df["licensed"] - df["ever_logged_in"]).clip(lower=0)
    df["dormant_30d"] = (df["licensed"] - df["active_30d"]).clip(lower=0)  # includes never logged in

    # without a ukid -> user_type mapping, per-type login numbers are unknown (not zero)
    if not Path(USER_MASTER).exists():
        per_type = ~df["user_type"].isin(["ALL", "unmapped"])
        df.loc[per_type, counts + ["never_logged_in", "dormant_30d",
                                   "app_share_pct", "browser_share_pct"]] = pd.NA

    # types not in ORDER (e.g. administrator, alumni) go at the end instead of becoming NaN
    extra = sorted(set(df["user_type"].dropna()) - set(ORDER))
    order = ORDER[:-1] + extra + ORDER[-1:]
    df["user_type"] = pd.Categorical(df["user_type"], order, ordered=True)
    df = df.sort_values(["tenant_id", "month", "user_type"])
    df["month_year"] = df["month"].dt.strftime("%b %Y")
    print(f"Login data starts {first_login_month}; 'never logged in' = no login since then.\n")
    return df[["tenant_id", "month_year", "user_type", "licensed", "avg_logged_in",
               "unique_logged_in", "ever_logged_in", "never_logged_in", "dormant_30d",
               "app_share_pct", "browser_share_pct"]]


if __name__ == "__main__":
    long = build()
    wide = long.pivot_table(index=["tenant_id", "month_year"], columns="user_type",
                            values=["licensed", "avg_logged_in", "never_logged_in", "dormant_30d",
                                    "app_share_pct", "browser_share_pct"],
                            aggfunc="first", observed=True, sort=False)
    wide.columns = [f"{ut}_{metric}" for metric, ut in wide.columns]
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print(long.to_string(index=False))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUTPUT) as xw:
        long.to_excel(xw, sheet_name="long", index=False)
        wide.to_excel(xw, sheet_name="wide")
    print(f"Saved: {OUTPUT}")