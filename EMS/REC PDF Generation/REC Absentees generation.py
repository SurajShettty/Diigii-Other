import pandas as pd
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm


def generate_absentee_pdf(df, output_path):

    # ---------------------------------------------
    # PDF STYLES
    # ---------------------------------------------
    styles = getSampleStyleSheet()

    college_name = "RAJALAKSHMI ENGINEERING COLLEGE(AUTONOMOUS), CHENNAI"

    header_style = ParagraphStyle(
        'header_style',
        parent=styles['Normal'],
        fontSize=14,
        alignment=1,
        spaceAfter=4,
        leading=16,
        bold=True
    )

    subheader_style = ParagraphStyle(
        'subheader_style',
        parent=styles['Normal'],
        fontSize=11,
        alignment=1,
        spaceAfter=2
    )

    title_style = ParagraphStyle(
        'title_style',
        parent=styles['Normal'],
        fontSize=15,
        alignment=1,
        spaceAfter=12,
        spaceBefore=8,
        leading=16,
        bold=True
    )

    wrap_style = ParagraphStyle(
        'wrap_style',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        wordWrap='CJK',
        maxLineLength=20
    )

    footer_style = ParagraphStyle(
        'footer_style',
        parent=styles['Normal'],
        fontSize=10,
        leading=14
    )

    footer_bold = ParagraphStyle(
        'footer_bold',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        bold=True
    )

    # ---------------------------------------------
    # PREPROCESSING
    # ---------------------------------------------
    df = df[df["date_of_exam"].notna()]


    df["session_str"] = df["start_time"].apply(
        lambda x: "FN" if str(x) < "12:00:00" else "AN"
    )

    df["exam_date"] = df.apply(
        lambda x: x["date_of_exam"].strftime("%d.%m.%Y") + f" ({x['session_str']})",
        axis=1
    )

    df["exam_title"] = df.apply(
        lambda x: f"{x['ems_schedule_name']} - {x['assessment_name']}",
        axis=1
    )

    exam_title = df.iloc[0]["exam_title"]
    # exam_date = df.iloc[0]["exam_date"]

    # ---------------------------------------------
    # GROUPING
    # ---------------------------------------------
    grouped = df.groupby(["department", "course_code","year"])

    absentee_rows = []
    sl_no = 1

    grand_total_students = 0
    grand_total_absent = 0
    grand_total_malpractice = 0  # NEW

    for (dept, course,year), sub_df in grouped:

        total_students = sub_df["attendance_status"].notna().sum()
        grand_total_students += total_students

        absentees = []

        for _, row in sub_df.iterrows():

            status = (str(row["attendance_status"]).strip().upper()
                      if pd.notna(row["attendance_status"]) else "")

            # ABSENT logic
            if "ABSENT" in status:
                absentees.append(str(row["reg_no"]))

            # MALPRACTICE logic
            elif status == "MALPRACTICE":
                absentees.append(str(row["reg_no"]) + "*")
                grand_total_malpractice += 1

        absentee_str = ", ".join(absentees)
        absentee_count = len(absentees)
        grand_total_absent += absentee_count

        absentee_rows.append([
            Paragraph(str(sl_no), wrap_style),
            Paragraph(str(year), wrap_style), 
            Paragraph(dept, wrap_style),
            Paragraph(course, wrap_style),
            Paragraph(str(total_students), wrap_style),
            Paragraph(absentee_str, wrap_style),
            Paragraph(str(absentee_count), wrap_style)
        ])

        sl_no += 1

    # ---------------------------------------------
    # CREATE PDF
    # ---------------------------------------------
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=80,
        rightMargin=80,
        topMargin=40,
        bottomMargin=30
    )

    elements = []

    # ---------------- Header ----------------
    elements.append(Paragraph(f"<b>{college_name}</b>", header_style))
    elements.append(Paragraph("OFFICE OF THE CONTROLLER OF EXAMINATIONS", subheader_style))
    elements.append(Paragraph(exam_title, subheader_style))
    # elements.append(Paragraph(exam_date, subheader_style))
    elements.append(Spacer(1, 18))

    elements.append(Paragraph("<b>ABSENTEES LIST</b>", title_style))
    elements.append(Spacer(1, 10))

    # ----------------------------------------
    # TABLE HEADER + DATA
    # ----------------------------------------
    table_data = [
        [
            Paragraph("<b>Sl.No</b>", wrap_style),
            Paragraph("<b>Year</b>", wrap_style),
            Paragraph("<b>Dept</b>", wrap_style),
            Paragraph("<b>Subject Code</b>", wrap_style),
            Paragraph("<b>Total No. of Candidates</b>", wrap_style),
            Paragraph("<b>Absentees Roll Number</b>", wrap_style),
            Paragraph("<b>Total Absentees</b>", wrap_style),
        ]
    ]

    table_data.extend(absentee_rows)

    # ----------------------------------------
    # MAIN TABLE
    # ----------------------------------------
    main_table = Table(
        table_data,
        colWidths=[1.2*cm, 1.2*cm, 5*cm, 2*cm, 3*cm, 6*cm, 1.5*cm]
    )

    main_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    # Outer table for spacing
    outer = Table([[main_table]], colWidths=[10*cm])
    outer.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(outer)
    elements.append(Spacer(1, 20))

    # ----------------------------------------
    # SUMMARY BELOW TABLE
    # ----------------------------------------
    elements.append(Paragraph(f"<b>Total Present :</b> {grand_total_students}", footer_style))
    elements.append(Paragraph(f"<b>Total Malpractice :</b> {grand_total_malpractice}", footer_style))
    elements.append(Paragraph(f"<b>Total Absentees (Including Malpractice):</b> {grand_total_absent}", footer_style))

    elements.append(Spacer(1, 15))

    # ----------------------------------------
    # FOOTER BLOCK
    # ----------------------------------------
    elements.append(Paragraph("CC To: All HOD'S", footer_style))
    elements.append(Paragraph("*= MAL PRACTICE", footer_style))
    elements.append(Spacer(1, 45))

    # AVAILABLE WIDTH
    page_width = A4[0] - (doc.leftMargin + doc.rightMargin)

    # Paragraph styles with zero indents
    footer_left = ParagraphStyle(
        'footer_left',
        parent=footer_bold,
        alignment=0,          # LEFT
        leftIndent=0,
        rightIndent=0,
        spaceBefore=0,
        spaceAfter=0
    )

    footer_right = ParagraphStyle(
        'footer_right',
        parent=footer_bold,
        alignment=2,          # RIGHT
        leftIndent=0,
        rightIndent=0,
        spaceBefore=0,
        spaceAfter=0
    )

    footer_table = Table(
        [
            [
                Paragraph("<b>CONTROLLER OF EXAMINATIONS</b>", footer_left),
                Paragraph("<b>PRINCIPAL</b>", footer_right)
            ]
        ],
        colWidths=[page_width/2, page_width/2]
    )

    footer_table.hAlign = 'LEFT'

    footer_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))


    elements.append(footer_table)
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "Note: HODs are requested to take necessary action to make the UG students "
        "attend the CAT / End Term EXAM without fail",
        footer_style
    ))

    # ----------------------------------------
    # BUILD PDF
    # ----------------------------------------
    doc.build(elements)
    print("\nPDF generated successfully:", output_path)



# -----------------------------------------------------------
# RUN SCRIPT
# -----------------------------------------------------------

if __name__ == "__main__":
    df = pd.read_excel("C:\\Users\\suraj\\OneDrive\\Desktop\\UG 2022 BATCH SEM VII EXAMINATIONS (ODD 2025-2026) 7th sem External Theory.xlsx")

    generate_absentee_pdf(df, "C:\\Users\\suraj\\OneDrive\\Desktop\\Absentees_List.pdf")
    print("DONE!")
