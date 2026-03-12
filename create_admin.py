#!/usr/bin/env python3
"""
One-time script to create an admin user in the local database.
Run from the simplex/ project root:

    python create_admin.py
"""

from app import create_app
from app.models import db, User

app = create_app()

with app.app_context():
    callsign = input("Enter callsign: ").strip().upper()
    password = input("Enter password: ").strip()

    if not callsign or not password:
        print("Callsign and password are required.")
        exit(1)

    existing = User.query.filter_by(callsign=callsign).first()
    if existing:
        print(f"User {callsign} already exists. Updating password.")
        existing.set_password(password)
        existing.is_active = True
        existing.is_admin  = True
    else:
        user = User(callsign=callsign, is_admin=True, is_active=True)
        user.set_password(password)
        db.session.add(user)

    db.session.commit()
    print(f"Admin user {callsign} saved successfully.")