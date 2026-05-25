import os
import pandas as pd

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle

# =========================================
# INPUT / OUTPUT
# =========================================

INPUT_EXCEL = r"C:\Users\suraj\Downloads\I-MAT Exam 2026_cleaned.xlsx"
OUTPUT_FOLDER = r"C:\Users\suraj\OneDrive\Desktop\I-MAT Exam 2026_cleaned OUTPUT_PDFS"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# =========================================
# READ DATA
# =========================================

df = pd.read_excel(INPUT_EXCEL)

# Replace NaN responses
df["response"] = df["response"].fillna("N/A")
df["option"] = df["option"].fillna("N/A")

# =========================================
# STYLES
# =========================================

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'title',
    parent=styles['Heading1'],
    alignment=TA_CENTER,
    fontSize=20,
    leading=25,
    spaceAfter=20
)

heading_style = styles['Heading2']
normal_style = styles['BodyText']

# =========================================
# GROUP STUDENT WISE
# =========================================

grouped = df.groupby("registration_id")

for student_id, student_df in grouped:

    student_df = student_df.reset_index(drop=True)

    # =========================================
    # STUDENT DETAILS
    # =========================================

    student_name = student_df.loc[0, "Name"]

    registration_id = student_df.loc[0, "registration_id"]

    programme_name = student_df.loc[0, "programme_name"]

    assessment_name = student_df.loc[0, "assessment_name"]

    assessment_date = student_df.loc[0, "assessment_date"]

    total_questions = len(student_df)

    total_marks = student_df["max_marks"].sum()

    obtained_marks = student_df["obtained_marks"].sum()

    pdf_path = os.path.join(
        OUTPUT_FOLDER,
        f"{registration_id}.pdf"
    )

    # =========================================
    # PDF DOCUMENT
    # =========================================

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []

    # =========================================
    # TITLE
    # =========================================

    elements.append(
        Paragraph("Assessment Answer Sheet", title_style)
    )

    elements.append(Spacer(1, 20))

    # =========================================
    # STUDENT INFO TABLE
    # =========================================

    student_table_data = [
        ["Student Name", str(student_name)],
        ["Registration ID", str(registration_id)],
        ["Programme", str(programme_name)],
        ["Assessment Name", str(assessment_name)],
        ["Assessment Date", str(assessment_date)],
    ]

    student_table = Table(
        student_table_data,
        colWidths=[180, 330]
    )

    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(student_table)

    elements.append(Spacer(1, 20))

    # =========================================
    # SUMMARY TABLE
    # =========================================

    summary_data = [
        ["Total Questions", total_questions],
        ["Total Marks", total_marks],
        ["Obtained Marks", obtained_marks]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[250, 150]
    )

    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#d9edf7")),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(summary_table)

    # =========================================
    # QUESTION 1 STARTS FROM PAGE 2
    # =========================================

    elements.append(PageBreak())

    # =========================================
    # QUESTION SECTION
    # =========================================

    for idx, row in student_df.iterrows():

        q_no = idx + 1

        elements.append(
            Paragraph(f"Question {q_no}", heading_style)
        )

        elements.append(Spacer(1, 10))

        question_table_data = [
            ["Question Type", str(row["question_type"])],
            ["Maximum Marks", str(row["max_marks"])],
            ["Marks Obtained", str(row["obtained_marks"])],
            ["Correct / Incorrect", str(row["correct/incorrect"])]
        ]

        q_table = Table(
            question_table_data,
            colWidths=[180, 320]
        )

        q_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(q_table)

        elements.append(Spacer(1, 12))

        question_text = f"""
        <b>Question:</b><br/>
        {row['question']}
        """

        # =========================================
        # RESPONSE LOGIC
        # =========================================

        response_value = row["response"]

        if response_value == "N/A":
            response_value = row["option"]

        response_text = f"""
        <b>Student Response:</b><br/>
        {response_value}
        """

        elements.append(
            Paragraph(question_text, normal_style)
        )

        elements.append(Spacer(1, 10))

        elements.append(
            Paragraph(response_text, normal_style)
        )

        elements.append(Spacer(1, 25))

    # =========================================
    # BUILD PDF
    # =========================================

    doc.build(elements)

    print(f"Generated PDF: {pdf_path}")

print("\nALL PDFs GENERATED SUCCESSFULLY")