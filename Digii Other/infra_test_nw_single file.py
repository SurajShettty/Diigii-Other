import pandas as pd

df_infra = pd.read_csv("C:\\Users\\suraj\\OneDrive\\Desktop\\infra_test_merged.csv")

df_infra["event_date"] = pd.to_datetime(df_infra["event_date"])

# Extract unique infra and dates
all_dates = df_infra["event_date"].sort_values().unique()
infra_ids = df_infra["infrastructure_id"].unique()

# Create full grid
full_grid = pd.MultiIndex.from_product(
    [infra_ids, all_dates],
    names=["infrastructure_id", "event_date"]
).to_frame(index=False)

# 1️⃣ Merge usage-level fields (date-based)
full_grid = full_grid.merge(
    df_infra[
        [
            "infrastructure_id",
            "event_date",
            "used_minutes",
            "lessons",
            "booking_type"
        ]
    ],
    on=["infrastructure_id", "event_date"],
    how="left"
)

# 2️⃣ Extract master-level attributes (same for all dates)
infra_master = df_infra[
    [
        "infrastructure_id",
        "infra_type",
        "venue",
        "building",
        "opening_time",
        "closing_time"
    ]
].drop_duplicates("infrastructure_id")

# 3️⃣ Merge master attributes INTO grid (non-date dependent)
full_grid = full_grid.merge(infra_master, on="infrastructure_id", how="left")

# 4️⃣ Determine default booking type
booking_pref = (
    df_infra.groupby("infrastructure_id")["booking_type"]
    .apply(lambda x: "Academic" if "Academic" in x.values else "Other")
)

infra_full_pref = pd.DataFrame({"infrastructure_id": infra_ids})
infra_full_pref = infra_full_pref.merge(
    booking_pref.rename("default_booking_type"),
    on="infrastructure_id",
    how="left"
).fillna({"default_booking_type": "Other"})

# 5️⃣ Apply default booking type for empty rows
full_grid = full_grid.merge(infra_full_pref, on="infrastructure_id", how="left")
full_grid["booking_type"] = full_grid["booking_type"].fillna(full_grid["default_booking_type"])
full_grid = full_grid.drop(columns=["default_booking_type"])

# Final column ordering
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
full_grid = full_grid[full_grid["event_date"].notna()]
# Save output
full_grid.to_excel("C:\\Users\\suraj\\OneDrive\\Desktop\\new.xlsx", index=False)

print("Final dataset created")
