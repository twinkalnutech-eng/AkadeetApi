import os
import json
from twilio.rest import Client
from dotenv import load_dotenv
from utils.utils import logger

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_SERVICE_ID = os.getenv("TWILIO_SERVICE_ID")   
TWILIO_CONTENT_SID = os.getenv("TWILIO_CONTENT_SID")


client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_whatsapp_with_pdf(
    mobile_no: str,
    pdf_file: str,  
    ticket_no: int,     
    total_tickets: int
):
    try:
        content_variables = json.dumps({
            "1": f"Ticket : {ticket_no}/{total_tickets}",
            "2": pdf_file    
        })

        message = client.messages.create(
            messaging_service_sid=TWILIO_SERVICE_ID,
            to=f"whatsapp:{mobile_no}",
            content_sid=TWILIO_CONTENT_SID,
            content_variables=content_variables
        )

        logger.info(f"WhatsApp sent successfully SID={message.sid}")

    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
