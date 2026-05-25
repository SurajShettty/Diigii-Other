import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak
import os

font_path = os.path.join(os.path.dirname(__file__), "NotoSansTamil-Regular.ttf")
pdfmetrics.registerFont(TTFont("NotoTamil", font_path))
pdfmetrics.registerFont(TTFont("NotoTamilBold", font_path))

def generate_attendance_pdfs(excel_file, college_name, logo_path):
    df = pd.read_excel(excel_file)

    df.columns = [c.lower() for c in df.columns]
    # Group by course, exam date, and time slot
    grouped = df.groupby(["department","course_code", "date_of_exam", "session_an_fn"])

    for (department,course_code, exam_date, session_from_excel), course_df in grouped:
        course_df = course_df.sort_values("reg_no").reset_index(drop=True)

        # Format date
        if pd.notna(exam_date):
            date_str = pd.to_datetime(exam_date).strftime("%d%m%Y")
        else:
            date_str = "NA"

        
        # Determine FN / AN
        session_code = session_from_excel if pd.notna(session_from_excel) else "NA"

        assessment_name =  course_df["assessment_name"].iloc[0]
        assessment_clean = str(assessment_name).replace(" ", "_").replace("/", "_")
        # Build final filename
        file_name = (
            f"C:\\Users\\suraj\\OneDrive\\Desktop\\New folder\\"
            f"Preexam_{department}_{course_code}_{date_str}_{session_code}_{assessment_clean}.pdf"
        )

        doc = SimpleDocTemplate(
            file_name,
            pagesize=A4,
            leftMargin=1.2 * cm,
            rightMargin=1.2 * cm,
            topMargin=0.7 * cm,
            bottomMargin=0.2 * cm
        )

        styles = getSampleStyleSheet()
        styles['Title'].fontSize = 16       # College name + schedule name
        styles['Title'].leading = 16        # Line spacing
        styles['Normal'].fontName = "Times-Roman"
        styles['Title'].fontName = "Times-Bold"
        styles['Heading3'].fontName = "Times-Bold"
        styles.add(ParagraphStyle(
            name="SmallHeader",
            parent=styles["Title"],
            fontSize=12,
            leading=12
        ))
        styles.add(ParagraphStyle(
            name="CourseTitleUnicode",
            parent=styles["Normal"],
            fontName="NotoTamil",
            fontSize=10,
            leading=12
        ))
        styles.add(ParagraphStyle(
            name="CourseTitleUnicodeBold",
            parent=styles["Normal"],
            fontName="NotoTamilBold",
            fontSize=10,
            leading=12
        ))
    


        story = []

        # Process 25 students per page
        for start in range(0, len(course_df), 25):

            # ➜ Force new page for every new chunk
            if start != 0:
                story.append(PageBreak())

            chunk = course_df.iloc[start:start + 25]

            # Pick values from Excel
            dept = chunk["department"].iloc[0]
            course_title = chunk["course_name"].iloc[0]
            course_code_value = chunk["course_code"].iloc[0]
            raw_date = chunk["date_of_exam"].iloc[0]

            # Convert to dd-mm-yyyy
            if pd.notna(raw_date):
                date_exam = pd.to_datetime(raw_date).strftime("%d-%m-%Y")
            else:
                date_exam = ""

            session = chunk["session"].iloc[0]
            
            semester = chunk["semester"].iloc[0]

            # ============================
            # HEADER WITH LOGO LEFT + CENTERED TEXT
            # ============================

            schedule_name = chunk["ems_schedule_name"].iloc[0]
            assessment_name = chunk["assessment_name"].iloc[0]
            raw_slot_date = chunk["date_of_exam"].iloc[0]

            if pd.notna(raw_slot_date):
                slot_date = pd.to_datetime(raw_slot_date).strftime("%B - %Y")
            else:
                slot_date = ""

            slot_start_time = str(chunk["start_time"].iloc[0]).strip()

            # Determine FN or AN
            session = session_from_excel if pd.notna(session_from_excel) else "NA"
            # try:
            #     # Convert to datetime no matter what format
            #     t = pd.to_datetime(slot_start_time, format=None).time()

            #     # FN before 12:00 PM else AN
            #     session = "FN" if t < pd.to_datetime("12:00", format="%H:%M").time() else "AN"

            # except Exception as e:
            #     print("Time parsing error:", slot_start_time, e)
            #     session = ""


            
            full_schedule_name = f"{schedule_name} - {assessment_name}"
            # full_slot = f"{slot_date}"
            # {slot_start_time} - {slot_end_time}"

            
            try:
                logo = Image(logo_path, width=50, height=50)
            except:
                logo = ""

            
            # New style for smaller schedule name
            # Add style only once
            if "ScheduleSmall" not in styles:
                styles.add(ParagraphStyle(
                    name="ScheduleSmall",
                    parent=styles["Title"],
                    fontSize=10,
                    leading=14
                ))


            # Create separate paragraphs
            header_html = f"""
            <para align='center'>
            <font size="14"><b>{college_name}</b></font><br/>
            <font size="12"><b>{full_schedule_name}</b></font><br/>
            
            <font size="12"><b>Attendance Sheet</b></font>
            </para>
            """
            # <font size="12"><b>{full_slot}</b></font><br/>

            header_para = Paragraph(header_html, styles["Normal"])


            header_table = Table(
                [[logo, header_para]],
                colWidths=[2.8 * cm, 13.7 * cm]
            )

            header_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (1,0), (1,0), 'CENTER'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ]))



            story.append(header_table)
            story.append(Spacer(1, 10))   


            # ============================
            # UNIFORM 3-COLUMN LAYOUT 
            # ============================

            full_width = 19 * cm   

            def make_three_col_row(col1, col2, col3):
                return Table(
                    [[ 
                        col1 if isinstance(col1, Paragraph) else Paragraph(col1, styles["Normal"]),
                        col2 if isinstance(col2, Paragraph) else Paragraph(col2, styles["Normal"]),
                        col3 if isinstance(col3, Paragraph) else Paragraph(col3, styles["Normal"]),
                    ]],
                    colWidths=[full_width * 0.50, full_width * 0.25, full_width * 0.25],
                    style=[('VALIGN', (0,0), (-1,-1), 'TOP')]
                )



            def make_three_col_line():
                return Table([[
                    "", "", ""
                ]], colWidths=[full_width * 0.55, full_width * 0.20, full_width * 0.25],
                style=TableStyle([
                    ('LINEBELOW', (0,0), (0,0), 0.7, colors.black),
                    ('LINEBELOW', (1,0), (1,0), 0.7, colors.black),
                    ('LINEBELOW', (2,0), (2,0), 0.7, colors.black),
                ]))

            

            # DEPARTMENT (Left)
            story.append(make_three_col_row(
                f"<b>Department:</b> {dept}",
                "",
                "<b>Regular / Arrear</b>"
            ))
            story.append(Spacer(1, 6))

            # COURSE TITLE / DATE OF EXAM
            story.append(make_three_col_row(
                # f"<b>Course Title:</b> {course_title}",
                # Paragraph(
                #     f"<font name='NotoTamilBold'>Course Title:</font> "
                #     f"<font name='NotoTamil'>{course_title}</font>",
                #     styles["Normal"]
                # ),
                Paragraph(
                    f"<b>Course Title:</b> <font name='NotoTamil'>{course_title}</font>",
                    styles["Normal"]
                ),
                "",
                f"<b>Date of Exam:</b> {date_exam}"
            ))
            story.append(Spacer(1, 6))

            # COURSE CODE / SESSION / SEMESTER
            story.append(make_three_col_row(
                f"<b>Course Code:</b> {course_code_value}",
                f"<b>Session:</b> {session}",
                f"<b>Semester:</b> {semester}"
            ))
            story.append(Spacer(1, 10))



            # ============================
            # MAIN TABLE WITH 10 COLUMNS
            # ============================
            header_absent = Paragraph("*Write AB for Absent", styles["Normal"])
            table_data = [
                [
                    "S. No", 
                    "Register No.", 
                    "Student Name",

                    "Answer Book No.", "", "", "", "",   

                    header_absent,
                    "Signature"
                ]
            ]


            for i, (idx, row) in enumerate(chunk.iterrows(), start=1):
                table_data.append([
                    start + i,                      
                    row["reg_no"],
                    Paragraph(str(row["student_name"]), styles["Normal"]),
                    "", "", "", "", "",
                    "",
                    ""
                ])      



            while len(table_data) < 26:
                table_data.append(["", "", "", "", "", "", "", "", "", ""])

            colWidths = [
                1.0 * cm,
                2.8 * cm,
                5.5 * cm,
                0.9 * cm, 0.9 * cm, 0.9 * cm, 0.9 * cm, 0.9 * cm,
                2.5 * cm,
                2.7 * cm
            ]

            table = Table(table_data, colWidths=colWidths)

            table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, -1), 'Times-Roman'),
                ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),

                # Enable wrap only for Student Name column
                
                ('WORDWRAP', (2, 0), (2, -1), True),
                ('VALIGN', (2, 1), (2, -1), 'TOP'),

                # Padding for cleaner wrapped text
                ('LEFTPADDING', (2,1), (2,-1), 3),
                ('RIGHTPADDING', (2,1), (2,-1), 3),

                # Merge Answer Book No.
                ('SPAN', (3,0), (7,0)),
                ('ALIGN', (3,0), (7,0), 'CENTER'),

                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ROWHEIGHT', (0, 0), (-1, -1), 18),
            ]))



            story.append(table)
            story.append(Spacer(1, 20))

            # ============================
            # TOTAL PRESENT / ABSENT
            # ============================

            total_line = Table([
                [
                    Paragraph("<b>Total Present:</b>", styles["Normal"]), "",
                    "",
                    Paragraph("<b>Total Absent:</b>", styles["Normal"]), ""
                ]
            ], colWidths=[4 * cm, 1 * cm, 7 * cm, 4 * cm, 1 * cm])

            total_line.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (3, 0), (3, 0), 'RIGHT'),
                ('BOX', (1, 0), (1, 0), 0.6, colors.black),
                ('BOX', (4, 0), (4, 0), 0.6, colors.black),
            ]))

            story.append(total_line)
            story.append(Spacer(1, 15))

            # ============================
            # SIGNATURE SECTIONS
            # ============================
            is_lab = "LAB" in str(assessment_name).upper()
            if is_lab:
                story.append(Paragraph("<b>Signature of the Internal Examiner with Date:</b> ____________________________", styles["Normal"]))
                story.append(Paragraph("Name & Designation: ___________________________________________", styles["Normal"]))
                story.append(Spacer(1, 15))
                story.append(Paragraph("<b>Signature of the External Examiner with Date:</b> ____________________________", styles["Normal"]))
                story.append(Paragraph("Name & Designation: ___________________________________________", styles["Normal"]))
                story.append(Spacer(1, 15))
                story.append(Paragraph("<b>Controller of Examinations:</b> ____________________________", styles["Normal"]))
                story.append(Spacer(1, 20))
            else:
                story.append(Paragraph("<b>Signature of the Invigilator's Signature with Date:</b> ____________________________", styles["Normal"]))
                story.append(Paragraph("Name & Designation: ___________________________________________", styles["Normal"]))
                story.append(Spacer(1, 15))
                story.append(Paragraph("<b>Controller of Examinations:</b> ____________________________", styles["Normal"]))
                story.append(Spacer(1, 20))

            # story.append(Paragraph("<b>Signature of the Internal Examiner with Date:</b> ____________________________", styles["Normal"]))
            # story.append(Paragraph("Name & Designation: ___________________________________________", styles["Normal"]))
            # story.append(Spacer(1, 15))

            # story.append(Paragraph("<b>Signature of the External Examiner with Date:</b> ____________________________", styles["Normal"]))
            # story.append(Paragraph("Name & Designation: ___________________________________________", styles["Normal"]))
            # story.append(Spacer(1, 15))

            # story.append(Paragraph("<b>Controller of Examinations:</b> ____________________________", styles["Normal"]))
            # story.append(Spacer(1, 20))

        doc.build(story)
        print(f"Generated: {file_name}")




generate_attendance_pdfs(
    excel_file="C:\\Users\\suraj\\OneDrive\\Desktop\\NOVDEC 2025 ESE PRACTICAL I SEMESTER.xlsx",
    college_name="RAJALAKSHMI ENGINEERING COLLEGE (AUTONOMOUS)",
    logo_path="C:\\Users\\suraj\\Downloads\\Picture1.png"   
)
