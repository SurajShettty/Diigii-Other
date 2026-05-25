import pandas as pd
import os
import glob

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader

from barcode import Code128
from barcode.writer import ImageWriter

from io import BytesIO

# =========================================================
# INPUT / OUTPUT FOLDERS
# =========================================================
INPUT_FOLDER = r"C:\Users\suraj\OneDrive\Desktop\FOE II year Even Semester (25-26)"

OUTPUT_FOLDER = r"C:\Users\suraj\OneDrive\Desktop\FOE II year Even Semester (25-26)_OUTPUT_PDFS"

# Create output folder if not exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# =========================================================
# PAGE
# =========================================================
PAGE_WIDTH, PAGE_HEIGHT = A4

# =========================================================
# TEMPLATE SETTINGS
# =========================================================
ROWS = 8
COLUMNS = 5

LEFT_MARGIN = 0.3 * cm
RIGHT_MARGIN = 0.3 * cm

TOP_MARGIN = 0.5 * cm
BOTTOM_MARGIN = 0

H_GAP = 0.225 * cm
V_GAP = 0

# =========================================================
# AUTO CALCULATE PERFECT HEIGHT
# =========================================================
AVAILABLE_HEIGHT = (
    PAGE_HEIGHT
    - TOP_MARGIN
    - BOTTOM_MARGIN
)

CELL_HEIGHT = AVAILABLE_HEIGHT / ROWS

CELL_WIDTH = 3.9 * cm

# =========================================================
# CALIBRATION
# =========================================================
OFFSET_X = 0 * cm
OFFSET_Y = 0 * cm

# =========================================================
# START POSITION
# =========================================================
START_X = LEFT_MARGIN + OFFSET_X
START_Y = PAGE_HEIGHT - TOP_MARGIN + OFFSET_Y

# =========================================================
# BARCODE SETTINGS
# =========================================================
BARCODE_WIDTH = 3.1 * cm
BARCODE_HEIGHT = 0.8 * cm

# =========================================================
# DEBUG
# =========================================================
DEBUG_BORDER = False

# =========================================================
# BARCODE GENERATOR
# =========================================================
def generate_barcode(value):

    buffer = BytesIO()

    options = {
        "module_width": 0.17,
        "module_height": 8,
        "quiet_zone": 0.1,
        "font_size": 0,
        "text_distance": 0,
        "write_text": False,
        "dpi": 300
    }

    barcode = Code128(
        value,
        writer=ImageWriter()
    )

    barcode.write(buffer, options)

    buffer.seek(0)

    return ImageReader(buffer)

# =========================================================
# GET ALL EXCEL FILES
# =========================================================
excel_files = glob.glob(os.path.join(INPUT_FOLDER, "*.xlsx"))

# =========================================================
# PROCESS EACH EXCEL FILE
# =========================================================
for excel_file in excel_files:

    print(f"\nProcessing: {excel_file}")

    # -----------------------------------------------------
    # FILE NAME
    # -----------------------------------------------------
    base_name = os.path.splitext(
        os.path.basename(excel_file)
    )[0]

    output_pdf = os.path.join(
        OUTPUT_FOLDER,
        f"{base_name}.pdf"
    )

    # -----------------------------------------------------
    # LOAD EXCEL
    # -----------------------------------------------------
    df = pd.read_excel(excel_file)

    # -----------------------------------------------------
    # SORT BY REGISTRATION ID
    # -----------------------------------------------------
    df = df.sort_values(
        by="Registration ID",
        ascending=True
    ).reset_index(drop=True)

    # -----------------------------------------------------
    # CREATE PDF
    # -----------------------------------------------------
    c = canvas.Canvas(
        output_pdf,
        pagesize=A4
    )

    c.setPageCompression(0)

    # =====================================================
    # PROCESS STUDENTS
    # =====================================================
    for index, row in df.iterrows():

        # -------------------------------------------------
        # NEW PAGE
        # -------------------------------------------------
        if index > 0 and index % ROWS == 0:
            c.showPage()

        # -------------------------------------------------
        # ROW POSITION
        # -------------------------------------------------
        row_num = index % ROWS

        y = START_Y - (
            row_num * CELL_HEIGHT
        )

        # -------------------------------------------------
        # DATA
        # -------------------------------------------------
        reg_id = str(row["Registration ID"])
        answer_sheet_id = str(row["Answer Sheet Number"])
        course = str(row["Course Code"])

        # =================================================
        # TEXT COLUMN
        # =================================================
        x = START_X

        if DEBUG_BORDER:
            c.rect(
                x,
                y - CELL_HEIGHT,
                CELL_WIDTH,
                CELL_HEIGHT
            )

        c.setFont("Helvetica", 7)

        c.drawString(
            x + 0.15 * cm,
            y - 0.7 * cm,
            reg_id
        )

        c.drawString(
            x + 0.15 * cm,
            y - 1.2 * cm,
            answer_sheet_id
        )

        c.drawString(
            x + 0.15 * cm,
            y - 1.7 * cm,
            course
        )

        # =================================================
        # BARCODE COLUMNS
        # =================================================
        for col in range(1, COLUMNS):

            x = START_X + (
                col * (CELL_WIDTH + H_GAP)
            )

            if DEBUG_BORDER:
                c.rect(
                    x,
                    y - CELL_HEIGHT,
                    CELL_WIDTH,
                    CELL_HEIGHT
                )

            barcode_img = generate_barcode(answer_sheet_id)

            # Barcode
            c.drawImage(
                barcode_img,
                x + 0.25 * cm,
                y - 1.25 * cm,
                width=BARCODE_WIDTH,
                height=BARCODE_HEIGHT,
                preserveAspectRatio=False,
                mask='auto'
            )

            # Text below barcode
            c.setFont("Helvetica", 7)

            c.drawCentredString(
                x + (CELL_WIDTH / 2),
                y - 1.9 * cm,
                answer_sheet_id
            )

    # =====================================================
    # SAVE PDF
    # =====================================================
    c.save()

    print(f"✅ Generated: {output_pdf}")

print("\n🎉 ALL PDFs GENERATED SUCCESSFULLY")