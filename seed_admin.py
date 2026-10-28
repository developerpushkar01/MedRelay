"""Create the first MedRelay platform administrator.

Run: python seed_admin.py
Set ADMIN_NAME, ADMIN_EMAIL and ADMIN_PASSWORD environment variables first.
"""
import os
from app import app, db, User

name = os.getenv("ADMIN_NAME", "MedRelay Administrator")
email = os.getenv("ADMIN_EMAIL", "admin@medrelay.local").strip().lower()
password = os.getenv("ADMIN_PASSWORD", "")

if not password:
    password = input("Choose a strong password for the admin account: ").strip()
if len(password) < 12:
    raise SystemExit("Admin password must be at least 12 characters.")

with app.app_context():
    db.create_all()
    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f"An account already exists for {email}. No changes made.")
    else:
        admin = User(full_name=name, email=email, role="admin")
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrator created: {email}")
