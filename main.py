from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
import os
import razorpay
from threading import Thread

from core.database import get_connection
from services.mail_service import send_ticket_email, send_email
from services.qr_pdf import create_ticket_pdf
from services.whatsapp_service import send_whatsapp_with_pdf
from api.validation_login import validate_user_credentials_in_db, validate_user_and_get_tickets
from utils.utils import decrypt_qr_data, generate_qr_string


load_dotenv()
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
IMAGE_BASE_PATH = os.path.join(os.getcwd(), "static", "ticket_images")
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL")  
BASE_DIR = os.getcwd()
IMAGE_BASE_PATH = os.path.join(BASE_DIR, "static", "ticket_images")
razorpay_client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
)


app = Flask(__name__)
CORS(app, origins=[
    "https://akadeet.com",
    "https://www.akadeet.com",
    "http://localhost:3000",
    "http://localhost:8138"
])

class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    return jsonify({"detail": e.detail}), e.status_code


@app.route("/", methods=["GET"])
def list_only_project_routes():
    routes = []

    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        methods = sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS"))
        routes.append({"path": str(rule), "methods": methods})

    return {
        "app": "AKADIT API",
        "status": "running",
        "total_routes": len(routes),
        "routes": routes
    }

@app.route("/health", methods=["GET"])
def health():
    try:
        conn = get_connection()
        conn.close()
        return {"status": "UP", "db": "connected"}
    except Exception as e:
        return {"status": "DOWN", "error": str(e)}

@app.route("/getEventList", methods=["GET"])
def get_ticketmaster():
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT
        TicketMasterId,
        EventDate,
        EventDay,
        Venue,
        Country,
        CountryCode,
        Currency,
        EntryDateTime,
        EntryUserMasterId,
        MaxLimit,
        EnquiryToEmailId,
        BCCEmailId,
        EventPostpone,
        EventClose,
        EventName,
        EventTime
    FROM TicketMaster
    WHERE EventDate >= CURDATE() 
    ORDER BY EventDate ASC
    """

    cursor.execute(query)

    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()

    data = [dict(zip(columns, row)) for row in rows]

    conn.close()

    return {
        "total_records": len(data),
        "tickets": data
    }


@app.route("/getEventTicketRate/<int:ticket_master_id>", methods=["GET"])
def get_event_rates(ticket_master_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            tm.TicketMasterId,
            tm.EventName,
            tc.TicketClassificationId,
            tc.TicketType,
            tc.TicketRate,
            tc.MinimumTickets
        FROM TicketMaster tm
        INNER JOIN TicketClassification tc
            ON tm.TicketMasterId = tc.TicketMasterId
        WHERE tm.TicketMasterId = ?
    """

    cursor.execute(query, ticket_master_id)

    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return {"message": "No data found for this event"}

    data = [dict(zip(columns, row)) for row in rows]

    conn.close()

    return {
        "TicketMasterId": ticket_master_id,
        "EventName": data[0]["EventName"],
        "TicketRates": [
            {
                "TicketClassificationId": d["TicketClassificationId"],
                "TicketType": d["TicketType"],
                "TicketRate": d["TicketRate"],
                "MinimumTickets": d["MinimumTickets"]
            }
            for d in data
        ]
    }


# =========================
# SAVE ENQUIRY API
# =========================
@app.route("/addTicketEnquiry", methods=["POST"])
def save_ticket_enquiry():
    body = request.get_json(force=True)
    ticket_master_id = body.get("ticket_master_id")
    name = body.get("name")
    mobile_no = body.get("mobile_no")
    email_id = body.get("email_id")
    ticket_count = body.get("ticket_count")

    if not isinstance(ticket_count, int) or ticket_count <= 0:
        raise HTTPException(status_code=400, detail="Invalid ticket count")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # =========================
        # 1. GET TICKET RATE
        # =========================
        cursor.execute("""
            SELECT TicketRate, MinimumTickets
            FROM TicketClassification
            WHERE TicketMasterId = %s
            LIMIT 1
        """, (ticket_master_id,))

        rate_row = cursor.fetchone()

        if not rate_row:
            raise HTTPException(status_code=404, detail="Ticket rate not found")

        ticket_rate = rate_row[0]
        minimum_tickets = rate_row[1]

        # =========================
        # 2. VALIDATE MINIMUM TICKETS
        # =========================
        if ticket_count < minimum_tickets:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum {minimum_tickets} tickets required"
            )

        # =========================
        # 3. CALCULATE TOTAL
        # =========================
        total_amount = ticket_rate * ticket_count

        # =========================
        # 4. INSERT ENQUIRY
        # =========================
        cursor.execute("""
            INSERT INTO TicketEnquiry
            (
                TicketMasterId,
                MobileNo,
                EmailId,
                TicketCount,
                TotalAmount,
                EntryDateTime,
                Name,
                IsSend
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            ticket_master_id,
            mobile_no,
            email_id,
            ticket_count,
            total_amount,
            datetime.now(),
            name,
            0
        ))

        conn.commit()

        return {
            "status": "success",
            "ticket_rate": ticket_rate,
            "ticket_count": ticket_count,
            "total_amount": total_amount,
            "message": "Ticket enquiry saved successfully"
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "detail": str(e)}, 500

    finally:
        cursor.close()
        conn.close()


def send_email_and_whatsapp(
    email_id,
    name,
    mobile_no,
    entry_datetime,
    ticket_count,
    total_amount,
    pdf_files
):
    # EMAIL
    send_ticket_email(
        email_id,
        name,
        mobile_no,
        entry_datetime,
        ticket_count,
        total_amount,
        "USD",
        "Event Name",
        None,
        pdf_files
    )

    # WHATSAPP (ONE MESSAGE PER TICKET)
    for i, pdf in enumerate(pdf_files, start=1):
        send_whatsapp_with_pdf(
            mobile_no=mobile_no,
            pdf_file=pdf,
            ticket_no=i,
            total_tickets=ticket_count
        )


@app.route("/qrScanner", methods=["POST"])
def scan_qr():
    body = request.get_json(force=True)
    qr_code = body.get("qrCode", "")
    conn = None
    cursor = None

    try:
        if not qr_code or not qr_code.strip():
            return {
                "status": 2,
                "message": "QR code cannot be empty"
            }

        try:
            decoded = decrypt_qr_data(qr_code)
        except Exception:
            return {
                "status": 2,
                "message": "Invalid QR code"
            }

        try:
            ticket_issue_id, details_id, ts = decoded.split("|")
            details_id = int(details_id)
        except Exception:
            return {
                "status": 2,
                "message": "Invalid QR code format"
            }
        
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT IsPersonEntered
            FROM TicketIssueDetails
            WHERE TicketIssueDetailsId = ?
        """, details_id)

        row = cursor.fetchone()

        if not row:
            return {
                "status": 2,
                "message": "Invalid ticket"
            }

        # ----------------------------
        # 5. Already used
        # ----------------------------
        if row.IsPersonEntered:
            return {
                "status": 1,
                "message": "Ticket already used"
            }

        # ----------------------------
        # 6. Mark entry
        # ----------------------------
        cursor.execute("""
            UPDATE TicketIssueDetails
            SET IsPersonEntered = 1,
                EntryDateTime = GETDATE()
            WHERE TicketIssueDetailsId = ?
        """, details_id)

        conn.commit()

        # ----------------------------
        # 7. Success
        # ----------------------------
        return {
            "status": 0,
            "message": "Entry allowed",
            "ticket_issue_id": int(ticket_issue_id),
            "ticket_issue_details_id": details_id
        }

    except Exception as e:
        return {
            "status": 2,
            "message": "Internal server error"
        }

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route("/userLogin", methods=["POST"])
def validate_user_credentials():
    body = request.get_json(force=True)
    try:
        is_valid = validate_user_credentials_in_db(
            body.get("username"),
            body.get("password")
        )

        if is_valid:
            return {
                "status": 1,
                "message": "Login successful"
            }

        return {
            "status": 0,
            "message": "Invalid username or password"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.route("/getReportData", methods=["POST"])
def scanner_login():
    body = request.get_json(force=True)

    result = validate_user_and_get_tickets(
        body.get("username"),
        body.get("password"),
        body.get("ticket_master_id")
    )

    if not result.is_valid_user:
        return {
            "success": False,
            "message": "Invalid username or password"
        }

    return {
        "tickets": result.tickets,
        "summary": result.summary
    }


@app.route("/banner_image", methods=["POST"])
def get_event_by_master_id():
    body = request.get_json(force=True)

    if body.get("ticket_master_id", 0) <= 0:
        raise HTTPException(status_code=400, detail="Invalid TicketMasterId")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                Image1,
                Image2,
                Image3,
                Image4,
                Image5,
                Image6
            FROM TicketMaster
            WHERE TicketMasterId = ?
        """, (body.get("ticket_master_id"),))

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Event not found")

        images = {}
        for i in range(1, 7):
            img = getattr(row, f"Image{i}", None)
            images[f"image{i}"] = f"{IMAGE_BASE_URL}/{body.get('ticket_master_id')}/{img}" if img else None

        return {"images": images}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()

@app.route("/addStallMaster", methods=["POST"])
def add_stall_master():
    body = request.get_json(force=True)
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO [EventManagement].[dbo].[StallMaster]
        (
            StallNo,
            EventMasterId,
            StallExpenses,
            Eminities,
            DepositAmount,
            EntryDateTime,
            EntryUserMasterId
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        cursor.execute(
            query,
            (
                body.get("stall_no"),
                body.get("event_master_id"),
                body.get("stall_expenses"),
                body.get("eminities"),
                body.get("deposit_amount"),
                datetime.now(),
                body.get("entry_user_master_id")
            )
        )

        conn.commit()

        return {
            "status": 1,
            "message": "Stall created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/addCategory", methods=["POST"])
def add_category():
    body = request.get_json(force=True)
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO [EventManagement].[dbo].[CategoryMaster]
        (
            CategoryName,
            CategoryType,
            EntryDateTime,
            EntryUserMasterId
        )
        VALUES (?, ?, ?, ?)
        """

        cursor.execute(
            query,
            (
                body.get("category_name"),
                body.get("category_type"),
                datetime.now(),
                body.get("entry_user_master_id")
            )
        )

        conn.commit()

        return {
            "status": 1,
            "message": "Category added successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route("/addStallBookingMaster", methods=["POST"])
def add_stall_booking_master():
    body = request.get_json(force=True)
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # --------------------------------
        # 1. CHECK EVENT EXISTS
        # --------------------------------
        cursor.execute(
            "SELECT TicketMasterId FROM TicketMaster WHERE TicketMasterId = %s",
            (body.get("EventMasterId"),)
        )
        if cursor.fetchone() is None:
            return {
                "status": 0,
                "message": "Invalid EventMasterId. Event not found."
            }, 400

        # --------------------------------
        # 2. INSERT STALL BOOKING
        # EntryDateTime is AUTO (DEFAULT CURRENT_TIMESTAMP)
        # --------------------------------
        insert_query = """
            INSERT INTO StallBookingMaster
            (
                EventMasterId,
                TenantName,
                TenantBrandName,
                TenantEmail,
                TenantContactNo,
                SocialMediaLink,
                CategoryId,
                IsExecutedBefore,
                SpecialRequirement,
                EntryUserMasterId
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        insert_values = (
            body.get("EventMasterId"),
            body.get("TenantName"),
            body.get("TenantBrandName"),
            body.get("TenantEmail"),
            body.get("TenantContactNo"),
            body.get("SocialMediaLink"),
            body.get("CategoryId"),
            1 if body.get("IsExecutedBefore") else 0,
            body.get("SpecialRequirement"),
            body.get("EntryUserMasterId")
        )

        cursor.execute(insert_query, insert_values)
        conn.commit()

        # --------------------------------
        # 3. GET LAST INSERT ID (MySQL)
        # --------------------------------
        cursor.execute("SELECT LAST_INSERT_ID()")
        stall_booking_id = cursor.fetchone()[0]

        # --------------------------------
        # 4. SEND CONFIRMATION EMAIL
        # --------------------------------
        if body.get("TenantEmail"):
            email_subject = "Stall Booking Confirmed"
            email_body = f"""
Hello {body.get('TenantName')},

Your stall booking has been successfully confirmed.

Booking Details:
Event ID: {body.get('EventMasterId')}
Tenant Name: {body.get('TenantName')}
Brand Name: {body.get('TenantBrandName')}
Contact No: {body.get('TenantContactNo')}
Category ID: {body.get('CategoryId')}
Special Requirement: {body.get('SpecialRequirement')}

Thank you,
Event Management Team
"""
            send_email(body.get("TenantEmail"), email_subject, email_body)

        return {
            "status": 1,
            "message": "Stall booking confirmed successfully",
            "StallBookingMasterId": stall_booking_id
        }

    except Exception as e:
        if conn:
            conn.rollback()
        return {
            "status": 0,
            "error": str(e)
        }, 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route("/getStallBookingMasters", methods=["GET"])
def get_stall_booking_masters():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
            SELECT 
                sbm.StallBookingMasterId,
                tm.EventName AS EventName,
                sbm.TenantName,
                sbm.TenantBrandName,
                sbm.TenantEmail,
                sbm.TenantContactNo,
                sbm.SocialMediaLink,
                cm.CategoryName AS CategoryName,
                sbm.IsExecutedBefore,
                sbm.SpecialRequirement,
                sbm.EntryDateTime
            FROM StallBookingMaster sbm
            LEFT JOIN TicketMaster tm
                ON sbm.EventMasterId = tm.TicketMasterId
            LEFT JOIN CategoryMaster cm
                ON sbm.CategoryId = cm.CategoryMasterId
            ORDER BY sbm.EntryDateTime DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # Convert rows to list of dicts
        columns = [col[0] for col in cursor.description]
        result = [dict(zip(columns, row)) for row in rows]

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route("/addSponsorMaster", methods=["POST"])
def add_sponsor_master():
    body = request.get_json(force=True)
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # ---------------------------
        # Insert Sponsor Master
        # ---------------------------
        query = """
            INSERT INTO SponsorMaster
            (
                EventMasterId,
                SponsorName,
                SponsorCompanyName,
                SponsorContactNo,
                SponsorEmail,
                ContactPersonName,
                ContactPersonDesignation,
                ContactPersonEmail,
                ContactPersonMobile,
                BusinessCategory,
                ApproximateBudget,
                InterestedSponsorCategory,
                EntryUserMasterId
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)

            SELECT SCOPE_IDENTITY();
        """

        cursor.execute(
            query,
            (
                body.get("EventMasterId"),
                body.get("SponsorName"),
                body.get("SponsorCompanyName"),
                body.get("SponsorContactNo"),
                body.get("SponsorEmail"),
                body.get("ContactPersonName"),
                body.get("ContactPersonDesignation"),
                body.get("ContactPersonEmail"),
                body.get("ContactPersonMobile"),
                body.get("BusinessCategory"),
                body.get("ApproximateBudget"),
                body.get("InterestedSponsorCategory"),
                body.get("EntryUserMasterId"),
                datetime.now()
            )
        )

        # Get inserted ID
        cursor.nextset()
        sponsor_master_id = cursor.lastrowid  

        conn.commit()

        # ---------------------------
        # Send Email (PLAIN TEXT)
        # ---------------------------
        if body.get("ContactPersonEmail"):
            email_subject = "Sponsor Booking Confirmed"

            email_body = f"""
        Dear {body.get('ContactPersonName')},

Your sponsor booking has been successfully confirmed.

Booking Details:
        Sponsor Name: {body.get('SponsorName')}
        Company Name: {body.get('SponsorCompanyName')}
        Event ID: {body.get('EventMasterId')}
        Business Category: {body.get('BusinessCategory')}
        Interested Sponsor Category: {body.get('InterestedSponsorCategory')}
        Approximate Budget: {body.get('ApproximateBudget')}
        Contact Person: {body.get('ContactPersonName')} ({body.get('ContactPersonDesignation')})

Thank you for partnering with us.

Regards,
Event Management Team
"""

            send_email(body.get("ContactPersonEmail"), email_subject, email_body)

        return {
            "status": 1,
            "message": "Sponsor added successfully and email sent",
            "SponsorMasterId": int(sponsor_master_id)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/getSponsorMasters", methods=["GET"])
def get_sponsor_masters():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)  # return dicts directly

        query = """
            SELECT
                sm.SponsorMasterId,
                tm.EventName AS EventName,
                sm.SponsorName,
                sm.SponsorCompanyName,
                sm.SponsorContactNo,
                sm.SponsorEmail,
                sm.ContactPersonName,
                sm.ContactPersonDesignation,
                sm.ContactPersonEmail,
                sm.ContactPersonMobile,
                sm.BusinessCategory,
                sm.ApproximateBudget,
                sm.InterestedSponsorCategory,
                sm.EntryDateTime
            FROM SponsorMaster sm
            LEFT JOIN TicketMaster tm
                ON sm.EventMasterId = tm.TicketMasterId
            ORDER BY sm.EntryDateTime DESC
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        return rows 

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/ticket/addTicketIssue", methods=["POST"])
def create_razorpay_order():
    body = request.get_json(force=True)
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1️⃣ Get ticket rate and minimum tickets
        cursor.execute("""
            SELECT TicketRate, MinimumTickets
            FROM TicketClassification
            WHERE TicketMasterId = %s AND TicketClassificationId = %s
            LIMIT 1
        """, (
            body.get("ticket_master_id"),
            body.get("ticket_classification_id")
        ))

        row = cursor.fetchone()
        if not row:
            return {"status": "error", "detail": "Invalid ticket"}, 400

        rate = float(row[0])
        min_tickets = int(row[1])

        ticket_count = int(body.get("ticket_count", 0))
        if ticket_count < min_tickets:
            return {"status": "error", "detail": f"Minimum {min_tickets} tickets required"}, 400

        total_amount = rate * ticket_count
        total_amount_paise = int(total_amount * 100)

        # 2️⃣ Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            "amount": total_amount_paise,
            "currency": "INR",
            "receipt": f"TICKET_{body.get('mobile_no')}"
        })
        

        # 3️⃣ Insert into TicketIssue
        cursor.execute("""
            INSERT INTO TicketIssue
            (
                TicketMasterId,
                MobileNo,
                EmailId,
                TicketCount,
                TotalAmount,
                EntryDateTime,
                Name,
                TransactionId
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            body.get("ticket_master_id"),
            body.get("mobile_no"),
            body.get("email_id"),
            ticket_count,
            total_amount,
            datetime.now(),
            body.get("name"),
            ""  # transaction id empty for now
        ))

        ticket_issue_id = cursor.lastrowid  # MySQL way to get inserted ID
        conn.commit()

        # 4️⃣ Return both IDs for frontend
        return {
            "order_id": razorpay_order["id"],
            "ticket_issue_id": ticket_issue_id
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "detail": str(e)}, 500

    finally:
        cursor.close()
        conn.close()


@app.route("/ticket/verifyPayment", methods=["POST"])
def verify_payment():
    body = request.get_json(force=True)
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                TicketMasterId,
                MobileNo,
                EmailId,
                TicketCount,
                TotalAmount,
                Name,
                TransactionId
            FROM TicketIssue
            WHERE TicketIssueId = ?
        """, body.get("ticket_issue_id"))

        row = cursor.fetchone()
        if not row:
            return {
                "status": 0,
                "message": "TicketIssue not found"
            }

        ticket_master_id = row.TicketMasterId
        mobile_no = row.MobileNo
        email_id = row.EmailId
        ticket_count = row.TicketCount
        total_amount = row.TotalAmount
        name = row.Name
        existing_transaction = row.TransactionId
        entry_datetime = datetime.now()

        if existing_transaction and existing_transaction.startswith("pay_"):
            return {
                "status": 0,
                "message": "Payment already processed"
            }

        # ----------------------------
        # Get Ticket Images 
        # ----------------------------
        cursor.execute("""
            SELECT Image5, Image6
            FROM TicketMaster
            WHERE TicketMasterId = ?
        """, ticket_master_id)

        img_row = cursor.fetchone()
        image5_path = None
        image6_path = None

        if img_row:
            if img_row.Image5:
                image5_path = os.path.join(IMAGE_BASE_PATH, img_row.Image5)
            if img_row.Image6:
                image6_path = os.path.join(IMAGE_BASE_PATH, img_row.Image6)

        cursor.execute("""
            UPDATE TicketIssue
            SET TransactionId = ?
            WHERE TicketIssueId = ?
        """, (
            body.get("razorpay_payment_id"),
            body.get("ticket_issue_id")
        ))

        pdf_files = []

        for i in range(1, ticket_count + 1):

            cursor.execute("""
                INSERT INTO TicketIssueDetails (TicketIssueId)
                OUTPUT INSERTED.TicketIssueDetailsId
                VALUES (?)
            """, body.get("ticket_issue_id"))

            details_id = int(cursor.fetchone()[0])

            qr_string = generate_qr_string(
                body.get("ticket_issue_id"),
                details_id
            )

            cursor.execute("""
                UPDATE TicketIssueDetails
                SET QRCode = ?
                WHERE TicketIssueDetailsId = ?
            """, (qr_string, details_id))

            pdf_path = create_ticket_pdf(
                ticket_issue_id=body.get("ticket_issue_id"),
                ticket_master_id=ticket_master_id,
                country_code="91",
                mobile_no=mobile_no,
                name=name,
                ticket_no=i,
                total_tickets=ticket_count,
                details_id=details_id,
                qr_code=qr_string,
                image5_path=image5_path, 
                image6_path=image6_path   
            )

            pdf_files.append(pdf_path)

        conn.commit()

        Thread(target=send_email_and_whatsapp, args=(
            email_id,
            name,
            mobile_no,
            entry_datetime,
            ticket_count,
            total_amount,
            pdf_files
        ), daemon=True).start()

        return {
            "status": 1,
            "message": "Payment verified and tickets issued successfully"
        }

    except Exception as e:
        conn.rollback()
        return {
            "status": 0,
            "message": f"Payment verification failed: {str(e)}"
        }

    finally:
        cursor.close()
        conn.close()

@app.route("/addTicketEnquiry", methods=["GET"])
def get_ticket_enquiry():

    return {"message": "Ticket enquiry API is working"} 
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
