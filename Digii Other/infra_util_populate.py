import pandas as pd

df_infra = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\infra all.csv")
df_book = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\infra_util_data.csv")

df_book["event_date"] = pd.to_datetime(df_book["event_date"])

all_dates = df_book["event_date"].sort_values().unique()
infra_ids = df_infra["infrastructure_version_id"].unique()

full_grid = pd.MultiIndex.from_product([infra_ids, all_dates],names=["infrastructure_id", "event_date"]).to_frame(index=False)

full_grid = full_grid.merge(
    df_infra.rename(columns={"infrastructure_version_id": "infrastructure_id"}),
    on="infrastructure_id",
    how="left"
)

full_grid = full_grid.merge(df_book,on=["infrastructure_id", "event_date"],how="left")


# Determine default booking type for each infra
booking_pref = (
    df_book.groupby("infrastructure_id")["booking_type"]
    .apply(lambda x: "Academic" if "Academic" in x.values else "Other")
)

infra_full_pref = pd.DataFrame({"infrastructure_id": infra_ids})
infra_full_pref = infra_full_pref.merge(booking_pref.rename("default_booking_type"),on="infrastructure_id",how="left")

# Fill missing booking types with "Other"
infra_full_pref["default_booking_type"] = infra_full_pref["default_booking_type"].fillna("Other")

# Merge into full_grid
full_grid = full_grid.merge(infra_full_pref,on="infrastructure_id",how="left")

# Apply default booking type to generated empty rows
full_grid["booking_type"] = full_grid["booking_type"].fillna(full_grid["default_booking_type"])

# Clean up helper column
full_grid = full_grid.drop(columns=["default_booking_type"])
full_grid = full_grid[
    [
        "infrastructure_id",
        "event_date",
        "used_minutes",
        "lessons",
        "booking_type",
        "infra_type",
        "venue",
        "building",
        "opening_time",
        "closing_time",
    ]
]

full_grid.to_excel("C:\\Users\\suraj\\OneDrive\\Desktop\\infra_util_final.xlsx", index=False)

print("Final dataset created")
