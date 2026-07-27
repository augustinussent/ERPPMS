ENDPOINTS = {
    "properties": {"method": "GET", "summary": "Assigned properties"},
    "availability": {"method": "GET", "summary": "Room-type availability", "query": ["property", "arrival_date", "departure_date"]},
    "create_reservation": {"method": "POST", "summary": "Create reservation", "idempotency": True},
    "reservation": {"method": "GET", "summary": "Reservation detail", "query": ["name"]},
    "room_status": {"method": "GET", "summary": "Room status", "query": ["property"]},
    "health": {"method": "GET", "summary": "Platform health"},
}
