from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return {"status": "Flask working"}

@app.route("/getEventList", methods=["GET"])
def get_tickets():
    return {"getEventList": []}  

@app.route("/getEventList/<int:ticket_id>", methods=["GET"])
def get_ticket(ticket_id: int):
    return {"ticket_id": ticket_id, "details": "Ticket details here"}

@app.route("/events_rates/<int:ticket_master_id>", methods=["GET"])
def get_events_rates(ticket_master_id: int):
    return {"ticket_master_id": ticket_master_id, "rates": []}

@app.route("/addTicketEnquiry", methods=["POST"])
def save_ticket_enquiry():
    body = request.get_json(force=True)
    return {"user_id": body.get("user_id"), "enquiries": []}

@app.route("/addTicketEnquiry", methods=["GET"])
def get_ticket_enquiry():
    return {"message": "Ticket enquiry API is working"}

@app.route("/addTicketIssue", methods=["POST"])
def create_ticket_issue():
    data = request.get_json(force=True)
    return {"message": "Ticket issue API is working"}
