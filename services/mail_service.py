from http import server
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()


def send_ticket_email(
    to_email: str,
    name: str,
    mobile_no: str,
    entry_datetime,
    ticket_count: int,
    total_amount: float,
    currency: str,
    event_name: str,
    bcc_email: str | None,
    pdf_files: list
):
    msg = MIMEMultipart("alternative")

    msg["From"] = os.getenv("EMAIL_FROM")
    msg["To"] = to_email
    msg["Subject"] = f"Ticket - {event_name} {mobile_no}"

    if bcc_email:
        msg["Bcc"] = bcc_email

    booking_time = entry_datetime.strftime("%d-%m-%Y %H:%M")

    # -------------------------
    # HTML BODY (LIKE IMAGE)
    # -------------------------
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px;">
        Dear <b>{name}</b>,<br/><br/>

        Greeting from <b>Akadeet Entertainment Corporation, North America</b><br/><br/>

        Your ticket confirmation details :<br/><br/>

        <table border="1" cellpadding="6" cellspacing="0"
               style="border-collapse: collapse; font-size: 14px;">
            <tr>
                <td><b>Booking Date Time</b></td>
                <td>{booking_time}</td>
            </tr>
            <tr>
                <td><b>Mobile No</b></td>
                <td>{mobile_no}</td>
            </tr>
            <tr>
                <td><b>Email Id</b></td>
                <td>{to_email}</td>
            </tr>
            <tr>
                <td><b>Ticket Count</b></td>
                <td>{ticket_count}</td>
            </tr>
            <tr>
                <td><b>Total Amount</b></td>
                <td>{total_amount:.2f} {currency}</td>
            </tr>
        </table>
        <br/><br/>

        Thank you for a being a valued participants.
        Please present this ticket while entering the venue.
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    # -------------------------
    # Attach PDFs
    # -------------------------
    for pdf_path in pdf_files:
        if not os.path.exists(pdf_path):
            continue

        with open(pdf_path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(pdf_path)
            )
            msg.attach(part)

    # -------------------------
    # Send Email
    # -------------------------
    with smtplib.SMTP(
        os.getenv("EMAIL_HOST"),
        int(os.getenv("EMAIL_PORT"))
    ) as server:
        server.starttls()
        server.login(
            os.getenv("EMAIL_USER"),
            os.getenv("EMAIL_PASSWORD")
        )
        server.send_message(msg)

    return True


def send_stall_booking_email(to_email: str, full_name: str, stall_no: str):
    msg = MIMEMultipart()
    msg["From"] = os.getenv("EMAIL_FROM")
    msg["To"] = to_email
    msg["Subject"] = "Stall Booking Confirmation"

    body = f"""
Hello {full_name},

Your stall booking has been successfully confirmed.

📍 Stall Number: {stall_no}

Thank you for booking with us.

Regards,
Event Management Team
"""
    msg.attach(MIMEText(body, "plain"))
    SMTP_HOST = os.getenv("EMAIL_HOST")
    SMTP_PORT = int(os.getenv("EMAIL_PORT"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
        server.send_message(msg)

def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = os.getenv("EMAIL_FROM")
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))
    SMTP_HOST = os.getenv("EMAIL_HOST")
    SMTP_PORT = int(os.getenv("EMAIL_PORT"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASSWORD"))
        server.send_message(msg)
    return True