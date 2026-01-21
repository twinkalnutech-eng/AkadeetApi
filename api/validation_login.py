from dataclasses import dataclass
import os
from datetime import datetime
from core.database import get_connection

@dataclass
class UserValidationResult:
    is_valid_user: bool
    is_report_visible: bool
    ticket_master_id: int = None


def validate_user_credentials_in_db(username: str, password: str) -> bool:
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1
            FROM TicketUserMaster
            WHERE UserName = ?
              AND Password = ?
        """, username, password)

        return cursor.fetchone() is not None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


pass

@dataclass
class ScannerLoginResult:
    is_valid_user: bool
    is_report_visible: bool = False
    ticket_master_id: int | None = None
    tickets: list | None = None
    summary: list | None = None


# --------------------------------
# MAIN FUNCTION
# --------------------------------
def validate_user_and_get_tickets(
    username: str,
    password: str,
    ticket_master_id: int
) -> ScannerLoginResult:

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # --------------------------------
        # 1. Validate User
        # --------------------------------
        cursor.execute("""
            SELECT
                TicketMasterId,
                IsReportVisible
            FROM TicketUserMaster
            WHERE UserName = ?
              AND Password = ?
        """, (username, password))

        user = cursor.fetchone()

        if not user:
            return ScannerLoginResult(is_valid_user=False)

        if user.TicketMasterId != ticket_master_id:
            return ScannerLoginResult(is_valid_user=False)

        # --------------------------------
        # 2. Fetch Ticket List (GROUPED + SUM)
        # --------------------------------
        cursor.execute("""
            SELECT
                TicketMasterId,
                MobileNo,
                EmailId,
                Name,
                SUM(TicketCount) AS TicketCount,
                SUM(TotalAmount) AS TotalAmount,
                MAX(EntryDateTime) AS EntryDateTime,
                MAX(TransactionId) AS TransactionId
            FROM TicketIssue
            WHERE TicketMasterId = ?
            GROUP BY
                TicketMasterId,
                MobileNo,
                EmailId,
                Name
            ORDER BY MAX(EntryDateTime) DESC
        """, (ticket_master_id,))

        tickets = []
        for row in cursor.fetchall():
            tickets.append({
                "ticketMasterId": row.TicketMasterId,
                "mobileNo": row.MobileNo,
                "emailId": row.EmailId,
                "name": row.Name,
                "ticketCount": row.TicketCount,
                "totalAmount": float(row.TotalAmount),
                "entryDateTime": (
                    row.EntryDateTime.strftime("%Y-%m-%d %H:%M:%S")
                    if isinstance(row.EntryDateTime, datetime) else None
                ),
                "transactionId": row.TransactionId
            })

        # --------------------------------
        # 3. Fetch Summary (UNCHANGED)
        # --------------------------------
        cursor.execute("""
            SELECT
                sub.TicketType,
                MAX(sub.TicketRate) AS TicketRate,
                SUM(sub.TicketCount) AS TotalTickets,
                SUM(sub.TotalAmount) AS TotalAmount
            FROM (
                SELECT
                    ti.TotalAmount / NULLIF(ti.TicketCount, 0) AS TicketRate,
                    ti.TicketCount,
                    ti.TotalAmount,
                    tc.TicketType,
                    ti.TicketMasterId
                FROM TicketIssue ti
                LEFT OUTER JOIN (
                    SELECT TicketRate, TicketType
                    FROM TicketClassification
                    WHERE TicketMasterId = ?
                ) tc
                ON tc.TicketRate = ti.TotalAmount / NULLIF(ti.TicketCount, 0)
            ) AS sub
            WHERE sub.TicketMasterId = ?
            GROUP BY sub.TicketType
        """, (ticket_master_id, ticket_master_id))

        summary = []
        for row in cursor.fetchall():
            summary.append({
                "ticketType": row.TicketType,
                "ticketRate": float(row.TicketRate) if row.TicketRate else 0,
                "totalTickets": row.TotalTickets,
                "totalAmount": float(row.TotalAmount)
            })

        # --------------------------------
        # 4. Final Response
        # --------------------------------
        return ScannerLoginResult(
            is_valid_user=True,
            is_report_visible=bool(user.IsReportVisible),
            ticket_master_id=ticket_master_id,
            tickets=tickets,
            summary=summary
        )

    finally:
        if cursor:
            cursor.close()
        if conn:

            conn.close()
