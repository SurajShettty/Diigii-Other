import html
import re
import pandas as pd

SRC = r"C:\Users\suraj\OneDrive\Desktop\JAIN EMS question report 14-06-2026.csv"
OUT = r"C:\Users\suraj\OneDrive\Desktop\JAIN EMS question report 14-06-2026_clean.xlsx"
COLS = ["question", "response_display", "selected_options"]

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")

def clean(val):
    if pd.isna(val):
        return val
    s = html.unescape(html.unescape(str(val)))  # double-decode
    s = TAG_RE.sub("", s)
    s = s.replace("\xa0", " ")
    s = WS_RE.sub(" ", s)
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())

df = pd.read_csv(SRC, low_memory=False)
for col in COLS:
    if col in df.columns:
        df[col] = df[col].apply(clean)
df.to_excel(OUT, index=False)
print(f"wrote {OUT} ({len(df)} rows)")
