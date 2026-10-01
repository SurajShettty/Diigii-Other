"""
Month-Year report by department and user type:
    Licensed users | Avg daily logged-in users | Never logged in | Dormant (no login in last 30 days)
    | App / Browser share of logins

Every month has one block per department (each user type + an ALL row), plus a
department = ALL block with the university-wide totals.

Sources
-------
license_user_summary_report.csv : daily licensed count per user_type / department_id (by programme)
login_report.csv                : one row per login (ukid = user id, timestamp)
user_master.csv  (OPTIONAL)     : ukid, user_type, department_id -> needed to split logins by
                                  user type / department, because login_report has neither
"""
from pathlib import Path
import importlib.util
import pandas as pd

SUMMARY = "C:\\Users\\suraj\\Downloads\\license_user_summary_report (1).csv"
LOGINS = "C:\\Users\\suraj\\Downloads\\login_report.csv"
USER_MASTER = "C:\\Users\\suraj\\Downloads\\user_details_report.csv"
OUTPUT = Path("C:\\Users\\suraj\\OneDrive\\Desktop\\final dataset summary.xlsx")
USER_OUTPUT = Path("C:\\Users\\suraj\\OneDrive\\Desktop\\final dataset user_level.csv")  # per-user dataset
FMT = "%d %b, %Y %H:%M:%S"
ORDER = ["student", "faculty", "staff", "parent", "prospective_student", "unmapped", "ALL"]
GROUP = ["tenant_id", "department_id", "user_type"]


def dept_str(s: pd.Series) -> pd.Series:
    """department_id as a clean string key ('90', not '90.0'); missing -> 'unmapped'."""
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str).replace("<NA>", "unmapped")


def rollup(df: pd.DataFrame) -> pd.DataFrame:
    """Add ALL rows for user_type, department and both, so totals use the same logic."""
    return pd.concat([df,
                      df.assign(user_type="ALL"),
                      df.assign(department_id="ALL"),
                      df.assign(department_id="ALL", user_type="ALL")], ignore_index=True)


# ---------- 1. Licensed per month (last available date in the month) ----------
def licensed_monthly() -> pd.DataFrame:
    s = pd.read_csv(SUMMARY)
    s["date"] = pd.to_datetime(s["logged_date"], format=FMT)
    s["department_id"] = dept_str(s["department_id"])
    daily = s.groupby(GROUP + ["date"], as_index=False)["count"].sum()
    daily["month"] = daily["date"].dt.to_period("M")
    last = daily.groupby(GROUP + ["month"])["date"].transform("max")
    lic = (daily[daily["date"] == last]
           .rename(columns={"count": "licensed"})[GROUP + ["month", "licensed"]])
    return rollup(lic).groupby(GROUP + ["month"], as_index=False)["licensed"].sum()


# ---------- 2. Logins ----------
def load_user_master() -> pd.DataFrame | None:
    if not Path(USER_MASTER).exists():
        return None
    um = pd.read_csv(USER_MASTER)[["ukid", "user_type", "department_id", "department_name"]]
    um = um.drop_duplicates("ukid")
    um["department_id"] = dept_str(um["department_id"])
    return um


def load_logins(um: pd.DataFrame | None) -> pd.DataFrame:
    lg = pd.read_csv(LOGINS)
    lg = lg[lg["success"].str.strip().str.lower().eq("yes")]
    lg["ts"] = pd.to_datetime(lg["timestamp"], format=FMT)
    lg["day"] = lg["ts"].dt.normalize()
    lg["month"] = lg["day"].dt.to_period("M")

    if um is not None:
        lg = lg.merge(um[["ukid", "user_type", "department_id"]], on="ukid", how="left")
        lg["user_type"] = lg["user_type"].fillna("unmapped").str.lower()
        lg["department_id"] = lg["department_id"].fillna("unmapped")
    else:
        lg["user_type"] = "unmapped"
        lg["department_id"] = "unmapped"
    return rollup(lg)


def login_monthly(lg: pd.DataFrame, months) -> pd.DataFrame:
    keys = GROUP + ["month"]
    daily = lg.drop_duplicates(GROUP + ["ukid", "day"])  # one row per user per day

    # avg logged in = sum of daily distinct users / days in month
    # (days with zero logins count; a partial current month uses days elapsed)
    dau = daily.groupby(keys)["ukid"].size().rename("user_days").reset_index()
    last_day = daily["day"].max()
    dau["days"] = dau["month"].apply(
        lambda m: last_day.day if m == last_day.to_period("M") else m.days_in_month)
    dau["avg_logged_in"] = (dau["user_days"] / dau["days"]).round(1)

    mau = daily.groupby(keys)["ukid"].nunique().rename("unique_logged_in").reset_index()

    # cumulative distinct users who have logged in at least once up to month end
    first = daily.groupby(GROUP + ["ukid"])["month"].min().reset_index()
    ever = pd.concat([
        first[first["month"] <= m].groupby(GROUP).size()
             .rename("ever_logged_in").reset_index().assign(month=m)
        for m in months])

    # distinct users with a login in the 30 days up to month end (or last data day)
    active = []
    for m in months:
        end = min(m.to_timestamp(how="end").normalize(), last_day)
        win = daily[(daily["day"] > end - pd.Timedelta(days=30)) & (daily["day"] <= end)]
        active.append(win.groupby(GROUP)["ukid"].nunique()
                         .rename("active_30d").reset_index().assign(month=m))
    active = pd.concat(active)

    # most recent login up to month end (may be from an earlier month)
    last_login = pd.concat([
        lg[lg["month"] <= m].groupby(GROUP)["ts"].max()
            .rename("last_login").reset_index().assign(month=m)
        for m in months])

    # share of login events by device (all logins, not deduped per day)
    is_app = lg["device_type"].str.strip().str.upper().eq("APP")
    dev = (lg.assign(is_app=is_app).groupby(keys)["is_app"].mean().mul(100).round(1)
             .rename("app_share_pct").reset_index())
    dev["browser_share_pct"] = (100 - dev["app_share_pct"]).round(1)

    return (dau[keys + ["avg_logged_in"]]
            .merge(mau, on=keys, how="outer")
            .merge(ever, on=keys, how="outer")
            .merge(active, on=keys, how="outer")
            .merge(last_login, on=keys, how="outer")
            .merge(dev, on=keys, how="outer"))


# ---------- 3. Combine ----------
def build() -> pd.DataFrame:
    um = load_user_master()
    lic = licensed_monthly()
    lg = load_logins(um)
    first_login_month = lg["month"].min()

    # only months covered by BOTH sources
    months = sorted(set(lic["month"]) & set(lg["month"]))
    lic = lic[lic["month"].isin(months)]
    log = login_monthly(lg, months)
    log = log[log["month"].isin(months)]

    df = lic.merge(log, on=GROUP + ["month"], how="outer")
    counts = ["avg_logged_in", "unique_logged_in", "ever_logged_in", "active_30d"]
    df[counts] = df[counts].fillna(0)
    df["never_logged_in"] = (df["licensed"] - df["ever_logged_in"]).clip(lower=0)
    df["dormant_30d"] = (df["licensed"] - df["active_30d"]).clip(lower=0)  # includes never logged in

    # without a ukid -> user_type / department mapping, split login numbers are unknown (not zero)
    if um is None:
        split = ~(df["user_type"].isin(["ALL", "unmapped"])
                  & df["department_id"].isin(["ALL", "unmapped"]))
        df.loc[split, counts + ["never_logged_in", "dormant_30d", "last_login",
                                "app_share_pct", "browser_share_pct"]] = pd.NA

    # department names from the user master; ids it doesn't know keep their id
    names = {} if um is None else (um.dropna(subset=["department_name"])
                                     .drop_duplicates("department_id")
                                     .set_index("department_id")["department_name"].to_dict())
    names.update({"ALL": "ALL", "unmapped": "unmapped"})
    df["department_name"] = df["department_id"].map(names).fillna("Department " + df["department_id"])

    # types not in ORDER (e.g. administrator, alumni) go at the end instead of becoming NaN
    extra = sorted(set(df["user_type"].dropna()) - set(ORDER))
    order = ORDER[:-1] + extra + ORDER[-1:]
    df["user_type"] = pd.Categorical(df["user_type"], order, ordered=True)
    depts = ["ALL"] + sorted(set(df["department_name"]) - {"ALL", "unmapped"}) + ["unmapped"]
    df["department_name"] = pd.Categorical(df["department_name"], depts, ordered=True)
    df = df.sort_values(["tenant_id", "month", "department_name", "user_type"])
    df["month_year"] = df["month"].dt.strftime("%b %Y")
    print(f"Login data starts {first_login_month}; 'never logged in' = no login since then.\n")
    return df[["tenant_id", "month_year", "department_id", "department_name", "user_type",
               "licensed", "avg_logged_in", "unique_logged_in", "ever_logged_in",
               "never_logged_in", "dormant_30d", "last_login", "app_share_pct", "browser_share_pct"]]


# ---------- 4. Per-user dataset (from GOI Licence dataset logic.py) ----------
def user_level() -> pd.DataFrame:
    path = Path(__file__).with_name("GOI Licence dataset logic.py")
    spec = importlib.util.spec_from_file_location("goi_licence", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    users = mod.build()

    # fill blank user_type and add department from the user master
    um = load_user_master()
    if um is not None:
        users = users.merge(um.rename(columns={"user_type": "um_user_type"}), on="ukid", how="left")
        users["user_type"] = users["user_type"].fillna(users.pop("um_user_type"))
        cols = list(users.columns)
        cols.insert(cols.index("college_id") + 1, cols.pop(cols.index("department_name")))
        cols.insert(cols.index("college_id") + 1, cols.pop(cols.index("department_id")))
        users = users[cols]
    return users


if __name__ == "__main__":
    long = build()
    users = user_level()
    wide = long.pivot_table(index=["tenant_id", "month_year", "department_id", "department_name"],
                            columns="user_type",
                            values=["licensed", "avg_logged_in", "never_logged_in", "dormant_30d",
                                    "last_login", "app_share_pct", "browser_share_pct"],
                            aggfunc="first", observed=True, sort=False)
    wide.columns = [f"{ut}_{metric}" for metric, ut in wide.columns]
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(long.to_string(index=False))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUTPUT) as xw:
        long.to_excel(xw, sheet_name="long", index=False)
        wide.to_excel(xw, sheet_name="wide")
        users.to_excel(xw, sheet_name="user_level", index=False)
    print(f"Saved: {OUTPUT}")
    users.to_csv(USER_OUTPUT, index=False)
    print(f"Saved: {USER_OUTPUT}")
