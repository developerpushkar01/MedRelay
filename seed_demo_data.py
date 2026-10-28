"""Create fictional MedRelay demo facilities, accounts, inventory and requests.

Run locally with: python seed_demo_data.py
For a public sandbox, set SEED_DEMO_DATA=1 to seed missing demo records at startup.
All demo accounts share the password documented in the README and homepage.
Do not use these credentials or sample records for real operations.
"""
from datetime import date, datetime, timedelta

from app import app, db, Facility, User, Medicine, InventoryItem, MedicineRequest

DEMO_PASSWORD = "MedRelayDemo2026!"

FACILITIES = [
    {
        "key": "hospital", "name": "Sunrise General Hospital", "type": "Hospital",
        "reg": "DEMO-MH-PN-H001", "address": "101 Sample Health Road",
        "city": "Pune", "state": "Maharashtra", "pincode": "411001",
        "lat": 18.5204, "lon": 73.8567,
        "user_name": "Demo Hospital Coordinator", "email": "demo.hospital@medrelay.local",
    },
    {
        "key": "clinic", "name": "Riverbend Community Clinic", "type": "Clinic",
        "reg": "DEMO-MH-PN-C002", "address": "22 Fictional Wellness Lane",
        "city": "Pune", "state": "Maharashtra", "pincode": "411004",
        "lat": 18.5074, "lon": 73.8077,
        "user_name": "Demo Clinic Coordinator", "email": "demo.clinic@medrelay.local",
    },
    {
        "key": "pharmacy", "name": "CarePlus Demo Pharmacy", "type": "Registered Pharmacy",
        "reg": "DEMO-MH-PN-P003", "address": "8 Example Market Street",
        "city": "Pune", "state": "Maharashtra", "pincode": "411005",
        "lat": 18.5308, "lon": 73.8475,
        "user_name": "Demo Pharmacy Coordinator", "email": "demo.pharmacy@medrelay.local",
    },
    {
        "key": "centre", "name": "NorthStar Medical Centre", "type": "Hospital",
        "reg": "DEMO-MH-PC-H004", "address": "55 Mock Care Avenue",
        "city": "Pimpri-Chinchwad", "state": "Maharashtra", "pincode": "411018",
        "lat": 18.6298, "lon": 73.7997,
        "user_name": "Demo Centre Coordinator", "email": "demo.centre@medrelay.local",
    },
]

MEDICINES = [
    {"key": "paracetamol", "name": "Paracetamol", "generic": "Paracetamol", "strength": "500 mg", "form": "Tablet", "unit": "tablets", "code": "DEMO-MED-001"},
    {"key": "ors", "name": "Oral Rehydration Salts", "generic": "Oral rehydration salts", "strength": "Standard sachet", "form": "Powder sachet", "unit": "sachets", "code": "DEMO-MED-002"},
    {"key": "cetirizine", "name": "Cetirizine", "generic": "Cetirizine", "strength": "10 mg", "form": "Tablet", "unit": "tablets", "code": "DEMO-MED-003"},
    {"key": "amoxicillin", "name": "Amoxicillin", "generic": "Amoxicillin", "strength": "250 mg", "form": "Capsule", "unit": "capsules", "code": "DEMO-MED-004"},
    {"key": "salbutamol", "name": "Salbutamol", "generic": "Salbutamol", "strength": "2 mg/5 ml", "form": "Syrup", "unit": "bottles", "code": "DEMO-MED-005"},
]


def seed_demo_data():
    """Insert demo rows only when their stable identifiers are missing."""
    facilities = {}
    for data in FACILITIES:
        facility = Facility.query.filter_by(registration_no=data["reg"]).first()
        if facility is None:
            facility = Facility(
                name=data["name"], facility_type=data["type"], registration_no=data["reg"],
                address=data["address"], city=data["city"], state=data["state"],
                pincode=data["pincode"], latitude=data["lat"], longitude=data["lon"],
                status="Approved",
            )
            db.session.add(facility)
            db.session.flush()
        else:
            facility.status = "Approved"
        facilities[data["key"]] = facility

        user = User.query.filter_by(email=data["email"]).first()
        if user is None:
            user = User(
                full_name=data["user_name"],
                email=data["email"],
                role="facility_admin",
                facility_id=facility.id,
            )
            user.set_password(DEMO_PASSWORD)
            user.is_active_account = True
            db.session.add(user)
        else:
            user.facility_id = facility.id
            user.role = "facility_admin"
            user.is_active_account = True
            # Reset the demo password for existing demo accounts too.
            user.set_password(DEMO_PASSWORD)

    medicines = {}
    for data in MEDICINES:
        medicine = Medicine.query.filter_by(medicine_code=data["code"]).first()
        if medicine is None:
            medicine = Medicine(
                name=data["name"], generic_name=data["generic"], strength=data["strength"],
                dosage_form=data["form"], unit=data["unit"], medicine_code=data["code"],
            )
            db.session.add(medicine)
            db.session.flush()
        medicines[data["key"]] = medicine

    # Batch numbers are stable so re-running the script will not duplicate inventory.
    inventory_rows = [
        ("pharmacy", "paracetamol", "DEMO-PAR-CP-001", 420),
        ("pharmacy", "ors", "DEMO-ORS-CP-001", 260),
        ("pharmacy", "cetirizine", "DEMO-CET-CP-001", 150),
        ("hospital", "paracetamol", "DEMO-PAR-SH-001", 180),
        ("hospital", "amoxicillin", "DEMO-AMX-SH-001", 75),
        ("centre", "ors", "DEMO-ORS-NS-001", 90),
        ("centre", "salbutamol", "DEMO-SAL-NS-001", 35),
    ]
    for facility_key, medicine_key, batch, quantity in inventory_rows:
        exists = InventoryItem.query.filter_by(batch_number=batch).first()
        if exists is None:
            db.session.add(InventoryItem(
                facility_id=facilities[facility_key].id,
                medicine_id=medicines[medicine_key].id,
                batch_number=batch,
                expiry_date=date.today() + timedelta(days=240),
                quantity_on_hand=quantity,
                reserved_quantity=0,
                stock_condition="Usable",
            ))

    # Seed example open requests once, so suppliers can try the marketplace.
    requests = [
        {
            "key": "clinic-ors", "facility": "clinic", "medicine": "ors", "qty": 80,
            "urgency": "High", "hours": 5,
            "reason": "[DEMO] Simulated request for a classroom workflow demonstration.",
        },
        {
            "key": "clinic-paracetamol", "facility": "clinic", "medicine": "paracetamol", "qty": 100,
            "urgency": "Critical", "hours": 3,
            "reason": "[DEMO] Fictional urgent request to demonstrate priority scoring and offers.",
        },
        {
            "key": "centre-cetirizine", "facility": "centre", "medicine": "cetirizine", "qty": 45,
            "urgency": "Routine", "hours": 48,
            "reason": "[DEMO] Sample routine request; no real patient or supply need is represented.",
        },
    ]
    for data in requests:
        existing = MedicineRequest.query.filter_by(reason=data["reason"]).first()
        if existing is None:
            required_by = datetime.utcnow() + timedelta(hours=data["hours"])
            from app import calculate_priority
            db.session.add(MedicineRequest(
                requesting_facility_id=facilities[data["facility"]].id,
                medicine_id=medicines[data["medicine"]].id,
                quantity_requested=data["qty"], quantity_fulfilled=0,
                urgency=data["urgency"], reason=data["reason"], required_by=required_by,
                status="Open", priority_score=calculate_priority(data["urgency"], required_by),
            ))

    db.session.commit()
    print("MedRelay demo data is ready.")
    print("Demo accounts use the same password: " + DEMO_PASSWORD)
    print("All facilities, inventory and requests are fictional demonstration data.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_demo_data()
