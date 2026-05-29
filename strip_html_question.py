import html
import re
import pandas as pd

SRC = r"C:\Users\suraj\Downloads\collpoll_iilmgg_ems_report202605280908.csv"
OUT = r"C:\Users\suraj\Downloads\collpoll_iilmgg_ems_report202605280908_clean.csv"
COL = "question"

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
df[COL] = df[COL].apply(clean)
df.to_csv(OUT, index=False)
print(f"wrote {OUT} ({len(df)} rows)")
