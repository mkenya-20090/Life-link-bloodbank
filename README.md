# 🩸 LifeLink Blood Bank Management System

A school project-grade Blood Bank Management System built with Flask, SQLite, and Chart.js.

## Project Structure
```
bloodbank/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── sample_admins.csv       # Sample CSV for admin import
├── instance/
│   └── bloodbank.db        # SQLite database (auto-created)
├── static/
│   ├── css/style.css       # All styles
│   └── js/main.js          # Frontend JavaScript
└── templates/
    ├── base.html            # Base layout
    ├── index.html           # Landing page
    ├── login.html           # Login
    ├── register.html        # Register
    ├── profile.html         # User profile
    ├── admin_dashboard.html # Admin dashboard + charts
    ├── admin_users.html     # Manage users
    ├── admin_requests.html  # Manage blood requests
    ├── admin_donations.html # Manage donations
    ├── admin_appointments.html # Manage appointments
    ├── import_admins.html   # Bulk import admins
    ├── donor_dashboard.html # Donor home
    ├── donor_donations.html # Donation history
    ├── donor_appointments.html # Book donation appt
    ├── recipient_dashboard.html # Recipient home
    ├── recipient_requests.html  # Blood requests
    ├── recipient_appointments.html # Book collection appt
    └── blood_match.html     # Compatible donor matching
```

## Database Schema
```sql
facilities (id, name, address, phone, created_at)
users      (id, name, email, password, phone, blood_group, role, facility_id, created_at)
donations  (id, donor_id, facility_id, donation_date, blood_group, units, status, notes, created_at)
blood_requests (id, recipient_id, blood_group, units, urgency, status, matched_donor_id, facility_id, request_date, notes, created_at)
appointments   (id, user_id, facility_id, appointment_date, appointment_time, type, status, notes, created_at)
```

## Setup & Run

### 1. Install Python 3.8+
Make sure Python is installed on your system.

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the application
```bash
python app.py
```

### 4. Open in browser
Visit: http://localhost:5000

## Default Admin Login
- **Email:** admin@bloodbank.com
- **Password:** admin123

## CSV Format for Admin Import
```csv
name,email,password,phone,blood_group,facility_id
Dr. Jane Smith,jane@hospital.com,pass123,555-1234,A+,1
```
Fields: name (required), email (required), password (default: admin123), phone, blood_group, facility_id (1=City General, 2=St Mary's, 3=Regional Blood Bank)

## Features
- Role-based access: Donor, Recipient, Admin
- Blood compatibility matching (ABO system)
- Appointment booking (donation & collection)
- Admin dashboard with Chart.js charts
- PDF report generation (donors, requests, summary)
- Bulk admin import via CSV
- Session-based authentication
