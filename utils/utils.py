import os
import base64
import logging
from dotenv import load_dotenv
from datetime import datetime
from Crypto.Cipher import AES

load_dotenv()

# -----------------------------
# LOGGING (SAFE & CORRECT)
# -----------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENCRPYTION_KEY = os.getenv("ENCRYPTION_KEY", "ThisIsA16ByteKey!")[:16].encode("utf-8")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("ticket-system")

# -----------------------------
# ENCRYPT / DECRYPT (QR PAYLOAD)
# -----------------------------
def encrypt_qr_data(data: str) -> str:
    """
    Simple reversible encryption for QR payload.
    Used only for obfuscation + tamper detection.
    """

    key = os.getenv("ENCRPYTION_KEY")
    if not key:
        raise RuntimeError("ENCRPYTION_KEY is not set in environment")

    payload = f"{data}|{key}"
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")
    return encoded


def decrypt_qr_data(encoded_data: str) -> str:
    """
    Decrypt and validate QR payload.
    Returns original data if valid.
    """

    try:
        decoded_bytes = base64.urlsafe_b64decode(encoded_data.encode("utf-8"))
        decoded_str = decoded_bytes.decode("utf-8")
    except Exception:
        logger.error("QR decode failed: Invalid Base64")
        raise ValueError("Invalid QR format")

    if "|" not in decoded_str:
        logger.error("QR decode failed: Invalid payload structure")
        raise ValueError("Invalid QR payload")

    data, key = decoded_str.rsplit("|", 1)
    expected_key = os.getenv("ENCRPYTION_KEY")

    if key != expected_key:
        logger.warning("QR validation failed: Key mismatch")
        raise ValueError("Invalid or tampered QR code")

    return data

def generate_qr_string(ticket_issue_id: int, details_id: int) -> str:
    """
    Creates encrypted QR payload to store in DB
    """
    raw_payload = f"{ticket_issue_id}|{details_id}|{int(datetime.utcnow().timestamp())}"

    cipher = AES.new(ENCRPYTION_KEY, AES.MODE_ECB)

    padded_data = raw_payload.encode("utf-8")
    padded_data += b" " * (16 - len(padded_data) % 16)

    encrypted = cipher.encrypt(padded_data)

    return base64.b64encode(encrypted).decode("utf-8")

logger = logging.getLogger("ticket-system")

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "ThisIsA16ByteKey!")[:16].encode("utf-8")

def decrypt_qr_data(encrypted_data: str) -> str:
    try:
        # Step 1: Base64 decode
        encrypted_bytes = base64.b64decode(encrypted_data)

        # Step 2: AES decrypt
        cipher = AES.new(ENCRYPTION_KEY, AES.MODE_ECB)
        decrypted = cipher.decrypt(encrypted_bytes)

        # Step 3: Remove padding
        decoded = decrypted.decode("utf-8").rstrip(" ")

        return decoded

    except Exception as e:
        logger.error(f"QR decode failed: {e}")
        raise ValueError("Invalid QR code")