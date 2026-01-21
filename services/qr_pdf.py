import os
import qrcode
from reportlab.lib.pagesizes import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from dotenv import load_dotenv
from utils.utils import encrypt_qr_data

load_dotenv()

QR_PATH = os.getenv("TICKET_QR_CODE_PATH", "./qrs") 
PDF_PATH = os.getenv("PDF_PATH", "./pdfs") 
os.makedirs(QR_PATH, exist_ok=True)
os.makedirs(PDF_PATH, exist_ok=True)


def generate_qr_code(ticket_master_id, country_code, mobile_no, details_id):
    details_id = int(details_id)
    details_str = f"{details_id:05d}"

    qr_raw = f"{ticket_master_id}{country_code}{mobile_no}{details_str}"
    encrypted_text = encrypt_qr_data(qr_raw)

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
    qr.add_data(encrypted_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    qr_file = os.path.join(QR_PATH, f"qr_{details_str}.png")
    img.save(qr_file)

    return qr_file

def generate_qr_code_with_details(ticket_master_id, country_code, mobile_no, details_id):
    details_id = int(details_id)
    details_str = f"{details_id:05d}"

    qr_raw = f"{ticket_master_id}{country_code}{mobile_no}{details_str}"
    encrypted_text = encrypt_qr_data(qr_raw)

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
    qr.add_data(encrypted_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    qr_file = os.path.join(QR_PATH, f"qr_{details_str}.png")
    img.save(qr_file)

    return qr_file, encrypted_text


def create_ticket_pdf(
    ticket_issue_id,
    ticket_master_id,
    country_code,
    mobile_no,
    name,
    ticket_no,
    total_tickets,
    qr_code,
    details_id,
    image5_path=None,
    image6_path=None
):
    qr_path = generate_qr_code(
        ticket_master_id, country_code, mobile_no, details_id
    )

    pdf_file = os.path.join(PDF_PATH, f"ticket_{details_id}.pdf")

    PAGE_WIDTH = 80 * mm
    PAGE_HEIGHT = 200 * mm

    c = canvas.Canvas(pdf_file, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

    # ==================================================
    # BACKGROUND IMAGE (TOP HEADER ONLY)
    # ==================================================
    HEADER_HEIGHT = 116 * mm

    if image5_path and os.path.exists(image5_path):
        c.drawImage(
            ImageReader(image5_path),
            0,
            PAGE_HEIGHT - HEADER_HEIGHT,
            PAGE_WIDTH,
            HEADER_HEIGHT,
            preserveAspectRatio=False,
            mask='auto'
        )

    # ==================================================
    # TEXT AREA (CENTER)
    # ==================================================
    TEXT_START_Y = PAGE_HEIGHT - HEADER_HEIGHT - 5 * mm

    # c.setFillColor(white)

    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_WIDTH / 2, TEXT_START_Y, "This ticket is valid for one person only")
    c.drawCentredString(PAGE_WIDTH / 2, TEXT_START_Y - 5*mm, "&")
    c.drawCentredString(PAGE_WIDTH / 2, TEXT_START_Y - 10*mm, "One-time entry.")

    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_WIDTH / 2, TEXT_START_Y - 15*mm, name)

    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_WIDTH / 2, TEXT_START_Y - 20*mm, mobile_no)

    c.setFont("Helvetica", 8)
    c.drawCentredString(
        PAGE_WIDTH / 2,
        TEXT_START_Y - 25*mm,
        f"Ticket {ticket_no} / {total_tickets}"
    )

    # ==================================================
    # QR CODE AREA (BOTTOM CENTER)
    # ==================================================
    QR_SIZE = 45 * mm
    QR_Y = 5 * mm

    c.drawImage(
        ImageReader(qr_path),
        (PAGE_WIDTH - QR_SIZE) / 2,
        QR_Y,
        QR_SIZE,
        QR_SIZE,
        mask='auto'
    )

    c.showPage()
    c.save()


    return pdf_file

