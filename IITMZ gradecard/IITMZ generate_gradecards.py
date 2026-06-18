"""
Generate IIT Madras style grade-card PDFs, one per student, from a CSV.

CSV schema (one row per COURSE). Student/semester fields are repeated on every
row that belongs to them; the script groups them automatically.

Student-level (same value on every row of a student):
    roll_no            e.g. ZDA24B039
    name               e.g. Aadi Kumbhar
    department         e.g. SCHOOL OF SCIENCE AND ENGINEERING
    degree             e.g. BACHELOR OF SCIENCE IN DATA SCIENCE AND ARTIFICIAL INTELLIGENCE
    total_registered   e.g. 152.00   (optional - computed from credits if blank)
    total_earned       e.g. 152.00   (optional - computed if blank)
    cgpa               e.g. 8.2       (final/overall CGPA shown in footer)

Semester-level (same value on every course row of that semester):
    sem_order          integer used only to order semesters (1,2,3,...)
    sem_name           e.g. First Semester
    sem_dates          e.g. October 2024 - February 2025
    sem_earned_credit  e.g. 47        (optional - computed from credits if blank)
    sem_gpa            e.g. 8.83
    sem_cgpa           e.g. 8.83

Course-level (one per row):
    course_code        e.g. Z1001
    title              e.g. Physics for Data Scientists
    cat                e.g. S          (category)
    cr                 e.g. 10         (credits)
    gr                 e.g. C          (grade)
    att                e.g. G          (attendance)

Usage:
    Edit the CSV_PATH / OUT_DIR / LOGO_PATH constants below, then run:
        python generate_gradecards.py
"""

import os
import re
import sys

import pandas as pd
from pypdf import PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ===========================================================================
# CONFIG -- edit these paths, then just run:  python generate_gradecards.py
# ===========================================================================
CSV_PATH = r"C:\Users\suraj\Downloads\iitmz transcript 18062026.csv"
OUT_DIR = r"C:\Users\suraj\OneDrive\Desktop\IITMZ"
LOGO_PATH = r"C:\Users\suraj\Downloads\iitmz.png"  # set to None if no logo
# Reference/legend image added as page 2 of every PDF (placed at native size).
PAGE2_PATH = r"C:\Users\suraj\OneDrive\Desktop\MCA Sem 3 Assignments\IITM Grade Card.pdf"  # set to None to skip

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
_styles = getSampleStyleSheet()

TITLE = ParagraphStyle(
    "title", parent=_styles["Normal"], fontName="Helvetica-Bold",
    fontSize=17, leading=19, alignment=TA_LEFT, textColor=colors.HexColor("#1f3864"),
)
INFO = ParagraphStyle(
    "info", parent=_styles["Normal"], fontName="Helvetica-Bold",
    fontSize=9, leading=13,
)
SEM_HDR = ParagraphStyle(
    "semhdr", parent=_styles["Normal"], fontName="Helvetica-Bold",
    fontSize=8.5, leading=10, alignment=TA_CENTER,
)
TH = ParagraphStyle(
    "th", parent=_styles["Normal"], fontName="Helvetica-Bold",
    fontSize=7.5, leading=9,
)
TD = ParagraphStyle(
    "td", parent=_styles["Normal"], fontName="Helvetica",
    fontSize=7.5, leading=8.5,
)
TD_C = ParagraphStyle("tdc", parent=TD, alignment=TA_CENTER)
SUMMARY = ParagraphStyle(
    "summary", parent=_styles["Normal"], fontName="Helvetica-Bold",
    fontSize=7.5, leading=9, alignment=TA_CENTER,
)
FOOT = ParagraphStyle(
    "foot", parent=_styles["Normal"], fontName="Helvetica",
    fontSize=7, leading=9,
)

# inner course-table column widths (within one semester block)
COL_W = [13 * mm, 38 * mm, 8 * mm, 8 * mm, 8 * mm, 8 * mm]  # Course,Title,Cat,Cr,Gr,Att
HEADERS = ["Course", "Title", "Cat", "Cr", "Gr", "Att"]


def _num(v):
    """Coerce a CSV cell to float, treating blank/NaN as None."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _fmt(v, decimals=2):
    n = _num(v)
    if n is None:
        return ""
    if decimals == 0:
        return str(int(round(n)))
    return f"{n:.{decimals}f}"


def _cell(v):
    s = "" if v is None else str(v).strip()
    # Treat NaN and lone placeholder marks ('.', '-') as empty.
    if s.lower() == "nan" or s in (".", "-", "--"):
        return ""
    return s


def build_column_header():
    """The Course/Title/Cat/Cr/Gr/Att header row, shown once at the top of
    each column (not repeated for every semester)."""
    # No internal rules here -- the bracketing black lines are drawn across the
    # full width by the outer grid (see build_student_story).
    tbl = Table([[Paragraph(h, TH) for h in HEADERS]], colWidths=COL_W)
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tbl


def build_semester_block(sem_name, sem_dates, courses, earned, gpa, cgpa):
    """Return a flowable for one semester sub-table (no column header row --
    the column header is rendered once at the top of each column)."""
    data = []

    # Semester title row (spans all columns)
    head = sem_name if not sem_dates else f"{sem_name} ({sem_dates})"
    data.append([Paragraph(head, SEM_HDR)] + [""] * (len(HEADERS) - 1))

    # Course rows
    for c in courses:
        data.append([
            Paragraph(_cell(c.get("course_code")), TD),
            Paragraph(_cell(c.get("title")), TD),
            Paragraph(_cell(c.get("cat")), TD_C),
            Paragraph(_fmt(c.get("cr"), 0), TD_C),
            Paragraph(_cell(c.get("gr")), TD_C),
            Paragraph(_cell(c.get("att")), TD_C),
        ])

    # Summary row (Earned Credit / GPA / CGPA)
    summary = (
        f"Earned Credit: {earned}&nbsp;&nbsp;&nbsp;"
        f"GPA: {gpa}&nbsp;&nbsp;&nbsp;CGPA: {cgpa}"
    )
    data.append([Paragraph(summary, SUMMARY)] + [""] * (len(HEADERS) - 1))

    tbl = Table(data, colWidths=COL_W)
    last = len(data) - 1
    tbl.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),          # semester title spans
        ("SPAN", (0, last), (-1, last)),    # summary spans
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, last), (-1, last), 5),
    ]))
    return tbl


def _native_image(path, max_w, max_h):
    """Image flowable at native size (1px = 1pt). Only shrinks if it would
    overflow the printable area; never enlarges -- 'placed as it is'."""
    iw, ih = ImageReader(path).getSize()
    scale = min(1.0, max_w / iw, max_h / ih)
    return Image(path, width=iw * scale, height=ih * scale)


def build_student_story(student, logo_path, page2_path=None):
    """Build the list of flowables for a single student's grade card."""
    story = []

    # ---- Header: logo + institute name -------------------------------------
    title_para = Paragraph("INDIAN INSTITUTE OF TECHNOLOGY MADRAS", TITLE)
    if logo_path and os.path.exists(logo_path):
        # Keep the logo's true aspect ratio (no squishing); fit it to ~22mm tall.
        lw, lh = ImageReader(logo_path).getSize()
        disp_h = 17 * mm
        disp_w = disp_h * lw / lh
        if disp_w > 70 * mm:                 # guard unusually wide logos
            disp_w = 70 * mm
            disp_h = disp_w * lh / lw
        logo = Image(logo_path, width=disp_w, height=disp_h)
        header = Table([[logo, title_para]], colWidths=[disp_w + 4, 186 * mm - disp_w - 4])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header)
    else:
        story.append(title_para)
    story.append(Spacer(1, 6))

    # ---- Student info ------------------------------------------------------
    story.append(Paragraph(
        f"Roll No: {student['roll_no']}&nbsp;&nbsp;&nbsp;&nbsp;"
        f"Name: {student['name']}", INFO))
    story.append(Paragraph(f"Department: {student['department']}", INFO))
    story.append(Paragraph(student["degree"], INFO))
    story.append(Spacer(1, 6))

    # ---- Semester blocks: 2-column grid -----------------------------------
    # Regular semesters flow column-major (left column first, then right):
    #   row1 = [Sem1, Sem3], row2 = [Sem2, Sem4], ...
    # Summer terms are pulled out and placed in their own row(s) at the bottom.
    def make_block(sem):
        return build_semester_block(
            sem["sem_name"], sem["sem_dates"], sem["courses"],
            sem["earned"], sem["gpa"], sem["cgpa"],
        )

    regular = [s for s in student["semesters"] if not s.get("is_summer")]
    summers = [s for s in student["semesters"] if s.get("is_summer")]
    reg_blocks = [make_block(s) for s in regular]
    sum_blocks = [make_block(s) for s in summers]

    if reg_blocks or sum_blocks:
        # Row 0 = the column header (shown once, at the top of each column).
        data = [[build_column_header(), build_column_header()]]

        # Regular semesters: left column = first half, right column = second half.
        half = (len(reg_blocks) + 1) // 2
        left_col, right_col = reg_blocks[:half], reg_blocks[half:]
        for r in range(half):
            left = left_col[r]
            right = right_col[r] if r < len(right_col) else ""
            data.append([left, right])

        # Summer terms: appended below, two per row.
        for i in range(0, len(sum_blocks), 2):
            left = sum_blocks[i]
            right = sum_blocks[i + 1] if i + 1 < len(sum_blocks) else ""
            data.append([left, right])

        col = 90 * mm
        grid = Table(data, colWidths=[col, col])
        grid.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),  # gap between semester rows
            # Two black lines bracketing the column-header row (full width).
            ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
            ("TOPPADDING", (0, 0), (-1, 0), 1),       # tight gap between the two lines
            ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ]))
        story.append(grid)

    story.append(Spacer(1, 8))

    # ---- Totals bar --------------------------------------------------------
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    totals = Table([[
        Paragraph(f"Total Credits Registered: {student['total_registered']}", INFO),
        Paragraph(f"Total Credits Earned: {student['total_earned']}", INFO),
        Paragraph(f"CGPA: {student['cgpa']}", INFO),
    ]], colWidths=[60 * mm, 60 * mm, 60 * mm])
    totals.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(totals)
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    story.append(Spacer(1, 10))

    # ---- Footnotes ---------------------------------------------------------
    notes = [
        "* Indicated credits are minimum requirements under each category. In addition, "
        "students are required to earn additional elective credits as per the curriculum "
        "under the above categories to meet the total credit requirement for award of Degree.",
        "&phi; Transfer credits are not included in Earned Credits and not considered for CGPA "
        "calculation. Transfer credits + Earned Credits should meet the Total Credit requirement.",
        f"Cumulative grade point average secured considering only the successfully completed "
        f"courses(credits) is {student['cgpa']}",
        "Min.Rq.Cr. = Credits required for award of degree.  E.Cr. = Earned credit till date "
        "of issue of grade card.",
    ]
    for n in notes:
        story.append(Paragraph(n, FOOT))
        story.append(Spacer(1, 4))

    # ---- Page 2: reference/legend IMAGE (native size) ----------------------
    # (A page-2 PDF is handled separately by merging -- see main().)
    if page2_path and os.path.exists(page2_path) and not page2_path.lower().endswith(".pdf"):
        story.append(PageBreak())
        avail_w = A4[0] - 24 * mm   # page width minus the 12mm left/right margins
        avail_h = A4[1] - 24 * mm
        story.append(_native_image(page2_path, avail_w, avail_h))

    return story


ORDINALS = [
    "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
    "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth",
]

# Logical field -> candidate header names (normalised: lowercase, spaces collapsed).
# Resolved against the real CSV so minor header differences / trailing spaces work.
COLUMN_CANDIDATES = {
    "roll_no":     ["registration id", "registrationid", "reg id", "roll no", "rollno"],
    "name":        ["student name", "name"],
    "department":  ["department", "dept"],
    "degree":      ["programm", "programme", "program", "degree"],
    "term_name":   ["term_name", "term name", "term"],
    "starts":      ["starts", "start date", "start_date"],
    "ends":        ["ends", "end date", "end_date"],
    "course_code": ["course code", "course_code", "coursecode"],
    "title":       ["course name", "course_name", "coursename", "title"],
    "cr":          ["course credits", "course credit", "credits", "credit"],
    "cat":         ["category", "cat"],
    "grade":       ["grade"],
    # The G / VG / Unknown band shown in the "Att" column lives in "Percentage Grade".
    # (attendance_percent holds the numeric %, which this layout does not display.)
    "att":         ["percentage grade", "attendance grade", "att grade"],
    "sgpa":        ["sgpa", "gpa"],
    "cgpa":        ["cgpa"],
    "earned":      ["earned points", "earned point", "earned credits",
                    "earned credit", "earned"],
}


def _norm(s):
    # Treat underscores and hyphens like spaces so "roll_no" == "roll no".
    return " ".join(str(s).strip().lower().replace("_", " ").replace("-", " ").split())


def resolve_columns(df):
    """Map each logical field to an actual column name in the dataframe."""
    norm_map = {_norm(c): c for c in df.columns}
    resolved, used = {}, set()

    # Pass 1: exact normalised match (so "Grade" wins before "Grade Points").
    for field, cands in COLUMN_CANDIDATES.items():
        for cand in cands:
            col = norm_map.get(_norm(cand))
            if col and col not in used:
                resolved[field], _ = col, used.add(col)
                break

    # Pass 2: substring match for anything still unresolved.
    for field, cands in COLUMN_CANDIDATES.items():
        if field in resolved:
            continue
        for cand in cands:
            cand_n = _norm(cand)
            for ncol, col in norm_map.items():
                if col not in used and cand_n in ncol:
                    resolved[field], _ = col, used.add(col)
                    break
            if field in resolved:
                break
    return resolved


def _parse_date(v):
    """Parse a date cell. ISO (YYYY-MM-DD) is read month-first; everything
    else (e.g. DD-MM-YYYY) is read day-first. Returns a Timestamp or None."""
    s = _cell(v)
    if not s:
        return None
    iso = bool(re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", s))
    try:
        return pd.to_datetime(s, dayfirst=not iso, errors="raise")
    except Exception:
        return None


def _fmt_date(v):
    """Format a date cell as 'Month YYYY'; fall back to the raw text."""
    dt = _parse_date(v)
    if dt is not None:
        return dt.strftime("%B %Y")
    return _cell(v) or None


_AY_RE = re.compile(r"AY\s*'?(\d{2})\s*-\s*'?(\d{2})", re.I)


def _academic_dates(term_name):
    """Standard academic-calendar date range derived from a term name like
    'Odd Sem AY 24-25 ...'. Returns e.g. 'October 2024 - February 2025', or
    None if the academic year / term type can't be determined.

        Odd Sem    AY a-b  ->  October a - February b
        Even Sem   AY a-b  ->  February b - July b
        Summer     AY a-b  ->  August b - October b
    """
    mt = _AY_RE.search(str(term_name))
    if not mt:
        return None
    y1, y2 = 2000 + int(mt.group(1)), 2000 + int(mt.group(2))
    t = str(term_name).lower()
    if "summer" in t:
        return f"August {y2} - October {y2}"
    if "odd" in t:
        return f"October {y1} - February {y2}"
    if "even" in t:
        return f"February {y2} - July {y2}"
    return None


def parse_students(df, cols):
    """Group the flat dataframe into nested student -> semester -> course."""
    df = df.fillna("")

    def g(row, field, default=""):
        c = cols.get(field)
        return row.get(c, default) if c else default

    def term_start(tdf):
        c = cols.get("starts")
        if c:
            dt = _parse_date(tdf.iloc[0][c])
            if dt is not None:
                return dt
        return pd.Timestamp.max

    roll_col = cols["roll_no"]
    term_col = cols.get("term_name")
    students = []

    for _, sdf in df.groupby(roll_col, sort=False):
        first = sdf.iloc[0]

        # Distinct terms (excluding blank term names), ordered by start date.
        terms = ([t for t in dict.fromkeys(sdf[term_col]) if _cell(t)]
                 if term_col else ["Semester"])
        terms = sorted(
            terms,
            key=lambda t: term_start(sdf[sdf[term_col] == t] if term_col else sdf),
        )

        semesters, total_earned, total_reg, last_cgpa = [], 0.0, 0.0, ""
        reg_count = 0          # counts only regular (non-summer) semesters
        for t in terms:
            tdf = sdf[sdf[term_col] == t] if term_col else sdf
            srow = tdf.iloc[0]
            is_summer = "summer" in str(t).lower()

            courses, sem_earned = [], 0.0
            for _, r in tdf.iterrows():
                code = _cell(g(r, "course_code"))
                title = _cell(g(r, "title"))
                cat = _cell(g(r, "cat"))
                grade = _cell(g(r, "grade"))
                crc = _cell(g(r, "cr"))
                # Skip only fully-empty rows. Keep a row that has any course data
                # (code, title, category, grade or credit) -- e.g. a summer term
                # that has a grade but no course name/code.
                if not (code or title or cat or grade or crc):
                    continue
                cr = _num(crc) or 0
                earned = _num(g(r, "earned"))
                earned = earned if earned is not None else cr
                sem_earned += earned
                total_reg += cr
                total_earned += earned
                courses.append({
                    "course_code": code,
                    "title": title,
                    "cat": cat,
                    "cr": crc,
                    "gr": grade,
                    "att": g(r, "att"),
                })

            # Keep a term if it has real courses, is a summer term, or carries
            # term-level GPA/CGPA (an in-progress term). Drop empty placeholders.
            gpa_v = _fmt(g(srow, "sgpa"), 2)
            cgpa_v = _fmt(g(srow, "cgpa"), 2)
            if not courses and not is_summer and not (gpa_v or cgpa_v):
                continue

            # Prefer the standard academic-calendar range derived from the term
            # name; fall back to the CSV start/end dates if it can't be derived.
            dates = _academic_dates(t)
            if not dates:
                sd, ed = _fmt_date(g(srow, "starts")), _fmt_date(g(srow, "ends"))
                dates = f"{sd} - {ed}" if sd and ed else (sd or "")
            if is_summer:
                label = "Summer Term"     # summers are not numbered
            else:
                label = (ORDINALS[reg_count] + " Semester"
                         if reg_count < len(ORDINALS) else f"Semester {reg_count + 1}")
                reg_count += 1
            last_cgpa = cgpa_v or last_cgpa

            semesters.append({
                "sem_name": label,
                "sem_dates": dates,
                "courses": courses,
                "earned": str(int(round(sem_earned))),
                "gpa": gpa_v,
                "cgpa": cgpa_v,
                "is_summer": is_summer,
            })

        students.append({
            "roll_no": _cell(g(first, "roll_no")).upper(),
            "name": _cell(g(first, "name")),
            "department": _cell(g(first, "department")),
            "degree": _cell(g(first, "degree")),
            "total_registered": f"{total_reg:.2f}",
            "total_earned": f"{total_earned:.2f}",
            "cgpa": last_cgpa,
            "semesters": semesters,
        })
    return students


def main():
    csv_path, out_dir = CSV_PATH, OUT_DIR
    logo_path, page2_path = LOGO_PATH, PAGE2_PATH

    if not os.path.exists(csv_path):
        sys.exit(f"CSV not found: {csv_path}")
    os.makedirs(out_dir, exist_ok=True)
    if logo_path and not os.path.exists(logo_path):
        print(f"Note: logo not found at {logo_path} -- rendering without it.")
        logo_path = None
    if page2_path and not os.path.exists(page2_path):
        print(f"Note: page-2 image not found at {page2_path} -- skipping page 2.")
        page2_path = None

    df = pd.read_csv(csv_path, dtype=str)
    cols = resolve_columns(df)

    print("Resolved columns:")
    for field in COLUMN_CANDIDATES:
        print(f"  {field:12s} -> {cols.get(field, '(not found)')}")

    for need in ("roll_no", "name", "course_code"):
        if need not in cols:
            sys.exit(f"Could not find a column for required field '{need}'. "
                     f"Available columns: {list(df.columns)}")

    page2_is_pdf = bool(page2_path) and page2_path.lower().endswith(".pdf")

    students = parse_students(df, cols)
    for st in students:
        safe = "".join(ch for ch in st["roll_no"] if ch.isalnum() or ch in "-_") or "student"
        out = os.path.join(out_dir, f"{safe}.pdf")
        doc = SimpleDocTemplate(
            out, pagesize=A4,
            leftMargin=12 * mm, rightMargin=12 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
            title=f"Grade Card - {st['roll_no']}",
        )
        doc.build(build_student_story(st, logo_path, page2_path))

        # If page 2 is a PDF, append its pages to the just-built grade card.
        if page2_is_pdf:
            merger = PdfWriter()
            merger.append(out)          # page 1 (the grade card we just wrote)
            merger.append(page2_path)   # page 2 (the legend PDF)
            with open(out, "wb") as fh:
                merger.write(fh)
            merger.close()

        print(f"  wrote {out}")

    print(f"Done. {len(students)} grade card(s) -> {out_dir}")


if __name__ == "__main__":
    main()
