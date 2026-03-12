from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file # pyright: ignore[reportMissingImports]
import sqlite3, os, csv, io
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash # pyright: ignore[reportMissingImports]
from reportlab.lib.pagesizes import A4 # pyright: ignore[reportMissingModuleSource]
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle # pyright: ignore[reportMissingModuleSource]
from reportlab.lib.units import inch # pyright: ignore[reportMissingModuleSource]
from reportlab.lib import colors # pyright: ignore[reportMissingModuleSource]
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable # pyright: ignore[reportMissingModuleSource]
import functools

app = Flask(__name__)
app.secret_key = "bloodbank_secret_2024"
DATABASE = os.path.join(os.path.dirname(__file__), "instance", "bloodbank.db")

BLOOD_COMPATIBILITY = {
    "A+":  ["A+","A-","O+","O-"],
    "A-":  ["A-","O-"],
    "B+":  ["B+","B-","O+","O-"],
    "B-":  ["B-","O-"],
    "AB+": ["A+","A-","B+","B-","AB+","AB-","O+","O-"],
    "AB-": ["A-","B-","AB-","O-"],
    "O+":  ["O+","O-"],
    "O-":  ["O-"],
}
BLOOD_GROUPS = ["A+","A-","B+","B-","AB+","AB-","O+","O-"]

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = get_db(); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS facilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, address TEXT, phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, phone TEXT, blood_group TEXT,
        role TEXT NOT NULL CHECK(role IN ('donor','recipient','admin')),
        facility_id INTEGER REFERENCES facilities(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS donations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id INTEGER NOT NULL REFERENCES users(id),
        facility_id INTEGER REFERENCES facilities(id),
        donation_date DATE NOT NULL, blood_group TEXT NOT NULL,
        units REAL DEFAULT 1.0,
        status TEXT DEFAULT 'completed' CHECK(status IN ('completed','pending','cancelled')),
        notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS blood_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_id INTEGER NOT NULL REFERENCES users(id),
        blood_group TEXT NOT NULL, units REAL DEFAULT 1.0,
        urgency TEXT DEFAULT 'normal' CHECK(urgency IN ('normal','urgent','critical')),
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','fulfilled','cancelled')),
        matched_donor_id INTEGER REFERENCES users(id),
        facility_id INTEGER REFERENCES facilities(id),
        request_date DATE NOT NULL, notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        facility_id INTEGER NOT NULL REFERENCES facilities(id),
        appointment_date DATE NOT NULL, appointment_time TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('donation','collection')),
        status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled','completed','cancelled')),
        notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    """)
    c.execute("SELECT COUNT(*) FROM facilities")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO facilities (name,address,phone) VALUES (?,?,?)", [
            ("City General Hospital","123 Main St, Downtown","555-0101"),
            ("St. Mary's Medical Center","456 Oak Ave, Westside","555-0202"),
            ("Regional Blood Bank","789 Pine Rd, Northgate","555-0303")])
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (name,email,password,phone,blood_group,role,facility_id) VALUES (?,?,?,?,?,?,?)",
                  ("Admin User","admin@bloodbank.com",generate_password_hash("admin123"),"555-0000","O+","admin",1))
    conn.commit(); conn.close()

init_db()

def login_required(f):
    @functools.wraps(f)
    def decorated(*args,**kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.","warning")
            return redirect(url_for("login"))
        return f(*args,**kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args,**kwargs):
            if "user_id" not in session: return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("Access denied.","danger")
                return redirect(url_for("dashboard"))
            return f(*args,**kwargs)
        return decorated
    return decorator

@app.route("/")
def index():
    if "user_id" in session: return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    conn = get_db()
    facilities = conn.execute("SELECT * FROM facilities").fetchall()
    conn.close()
    if request.method == "POST":
        name=request.form["name"].strip(); email=request.form["email"].strip().lower()
        password=request.form["password"]; phone=request.form.get("phone","").strip()
        blood_group=request.form.get("blood_group",""); role=request.form.get("role","donor")
        facility_id=request.form.get("facility_id") or None
        if not name or not email or not password:
            flash("Name, email and password are required.","danger")
            return render_template("register.html",facilities=facilities,blood_groups=BLOOD_GROUPS)
        conn=get_db()
        if conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone():
            flash("Email already registered.","danger"); conn.close()
            return render_template("register.html",facilities=facilities,blood_groups=BLOOD_GROUPS)
        conn.execute("INSERT INTO users (name,email,password,phone,blood_group,role,facility_id) VALUES (?,?,?,?,?,?,?)",
                     (name,email,generate_password_hash(password),phone,blood_group,role,facility_id))
        conn.commit(); conn.close()
        flash("Registration successful! Please log in.","success")
        return redirect(url_for("login"))
    return render_template("register.html",facilities=facilities,blood_groups=BLOOD_GROUPS)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email=request.form["email"].strip().lower(); password=request.form["password"]
        conn=get_db(); user=conn.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); conn.close()
        if user and check_password_hash(user["password"],password):
            session.update({"user_id":user["id"],"name":user["name"],"role":user["role"],"blood_group":user["blood_group"],"facility_id":user["facility_id"]})
            flash(f"Welcome back, {user['name']}!","success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); flash("You have been logged out.","info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    role=session["role"]; uid=session["user_id"]; conn=get_db()
    if role=="admin":
        stats={
            "total_users":conn.execute("SELECT COUNT(*) FROM users WHERE role!='admin'").fetchone()[0],
            "total_donations":conn.execute("SELECT COUNT(*) FROM donations").fetchone()[0],
            "pending_requests":conn.execute("SELECT COUNT(*) FROM blood_requests WHERE status='pending'").fetchone()[0],
            "total_appointments":conn.execute("SELECT COUNT(*) FROM appointments WHERE status='completed'").fetchone()[0],
        }
        blood_dist=conn.execute("SELECT blood_group,SUM(units) as cnt FROM donations WHERE status='completed' GROUP BY blood_group ORDER BY blood_group").fetchall()
        monthly=conn.execute("SELECT strftime('%Y-%m',donation_date) as month,COUNT(*) as cnt FROM donations GROUP BY month ORDER BY month DESC LIMIT 6").fetchall()
        recent_requests=conn.execute("SELECT br.*,u.name as recipient_name FROM blood_requests br JOIN users u ON br.recipient_id=u.id ORDER BY br.created_at DESC LIMIT 5").fetchall()
        conn.close()
        blood_dist_dict = {row['blood_group']: row['cnt'] for row in blood_dist}
        blood_group_counts = [blood_dist_dict.get(bg, 0) for bg in BLOOD_GROUPS]
        months = [row['month'] for row in reversed(monthly)]
        monthly_donations = [row['cnt'] for row in reversed(monthly)]
        return render_template("admin_dashboard.html",stats=stats,blood_dist=blood_dist,monthly=monthly,recent_requests=recent_requests,blood_groups=BLOOD_GROUPS,blood_group_counts=blood_group_counts,months=months,monthly_donations=monthly_donations)
    elif role=="donor":
        donations=conn.execute("SELECT d.*,f.name as facility_name FROM donations d LEFT JOIN facilities f ON d.facility_id=f.id WHERE d.donor_id=? ORDER BY d.donation_date DESC LIMIT 5",(uid,)).fetchall()
        appointments=conn.execute("SELECT a.*,f.name as facility_name FROM appointments a JOIN facilities f ON a.facility_id=f.id WHERE a.user_id=? AND a.status='scheduled' ORDER BY a.appointment_date",(uid,)).fetchall()
        total_donations=conn.execute("SELECT COUNT(*) FROM donations WHERE donor_id=?",(uid,)).fetchone()[0]
        total_appointments=conn.execute("SELECT COUNT(*) FROM appointments WHERE user_id=? AND status='completed'",(uid,)).fetchone()[0]
        stats={"total_donations":total_donations, "upcoming_appointments":len(appointments), "completed_appointments":total_appointments, "lives_saved":total_donations*3}
        conn.close()
        return render_template("donor_dashboard.html",donations=donations,appointments=appointments,total_donations=total_donations,stats=stats)
    else:
        requests_list=conn.execute("SELECT br.*,f.name as facility_name FROM blood_requests br LEFT JOIN facilities f ON br.facility_id=f.id WHERE br.recipient_id=? ORDER BY br.created_at DESC LIMIT 5",(uid,)).fetchall()
        appointments=conn.execute("SELECT a.*,f.name as facility_name FROM appointments a JOIN facilities f ON a.facility_id=f.id WHERE a.user_id=? AND a.status='scheduled' ORDER BY a.appointment_date",(uid,)).fetchall()
        active_requests=conn.execute("SELECT COUNT(*) FROM blood_requests WHERE recipient_id=? AND status!='fulfilled'",(uid,)).fetchone()[0]
        fulfilled_requests=conn.execute("SELECT COUNT(*) FROM blood_requests WHERE recipient_id=? AND status='fulfilled'",(uid,)).fetchone()[0]
        stats={"active_requests":active_requests, "upcoming_appointments":len(appointments), "fulfilled_requests":fulfilled_requests}
        conn.close()
        return render_template("recipient_dashboard.html",requests=requests_list,appointments=appointments,stats=stats)

@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    uid=session["user_id"]; conn=get_db()
    facilities=conn.execute("SELECT * FROM facilities").fetchall()
    if request.method == "POST":
        name=request.form["name"].strip(); phone=request.form.get("phone","").strip(); blood_group=request.form.get("blood_group","")
        conn.execute("UPDATE users SET name=?,phone=?,blood_group=? WHERE id=?",(name,phone,blood_group,uid))
        conn.commit(); session["name"]=name; session["blood_group"]=blood_group
        flash("Profile updated successfully.","success")
    user=conn.execute("SELECT u.*,f.name as facility_name FROM users u LEFT JOIN facilities f ON u.facility_id=f.id WHERE u.id=?",(uid,)).fetchone()
    conn.close()
    return render_template("profile.html",user=user,facilities=facilities,blood_groups=BLOOD_GROUPS)

@app.route("/donor/donations")
@login_required
@role_required("donor")
def donor_donations():
    uid=session["user_id"]; conn=get_db()
    donations=conn.execute("SELECT d.*,f.name as facility_name FROM donations d LEFT JOIN facilities f ON d.facility_id=f.id WHERE d.donor_id=? ORDER BY d.donation_date DESC",(uid,)).fetchall()
    conn.close()
    return render_template("donor_donations.html",donations=donations)

@app.route("/donor/appointments", methods=["GET","POST"])
@login_required
@role_required("donor")
def donor_appointments():
    uid=session["user_id"]; conn=get_db()
    facilities=conn.execute("SELECT * FROM facilities").fetchall()
    if request.method == "POST":
        fid=request.form["facility_id"]; dt=request.form["appointment_date"]; tm=request.form["appointment_time"]; notes=request.form.get("notes","")
        if dt < date.today().isoformat():
            flash("Cannot book appointment in the past.","danger")
        else:
            conn.execute("INSERT INTO appointments (user_id,facility_id,appointment_date,appointment_time,type,notes) VALUES (?,?,?,?,?,?)",(uid,fid,dt,tm,"donation",notes))
            conn.commit(); flash("Appointment booked!","success")
            return redirect(url_for("donor_appointments"))
    appointments=conn.execute("SELECT a.*,f.name as facility_name FROM appointments a JOIN facilities f ON a.facility_id=f.id WHERE a.user_id=? ORDER BY a.appointment_date DESC",(uid,)).fetchall()
    conn.close()
    return render_template("donor_appointments.html",appointments=appointments,facilities=facilities,today=date.today().isoformat())

@app.route("/recipient/requests", methods=["GET","POST"])
@login_required
@role_required("recipient")
def recipient_requests():
    uid=session["user_id"]; conn=get_db()
    facilities=conn.execute("SELECT * FROM facilities").fetchall()
    if request.method == "POST":
        bg=request.form["blood_group"]; units=float(request.form.get("units",1.0))
        urgency=request.form.get("urgency","normal"); fid=request.form.get("facility_id") or None
        notes=request.form.get("notes","")
        conn.execute("INSERT INTO blood_requests (recipient_id,blood_group,units,urgency,facility_id,request_date,notes) VALUES (?,?,?,?,?,?,?)",(uid,bg,units,urgency,fid,date.today().isoformat(),notes))
        conn.commit(); flash("Blood request submitted!","success")
        return redirect(url_for("recipient_requests"))
    requests_list=conn.execute("SELECT br.*,f.name as facility_name,u.name as matched_donor_name FROM blood_requests br LEFT JOIN facilities f ON br.facility_id=f.id LEFT JOIN users u ON br.matched_donor_id=u.id WHERE br.recipient_id=? ORDER BY br.created_at DESC",(uid,)).fetchall()
    conn.close()
    return render_template("recipient_requests.html",requests=requests_list,facilities=facilities,blood_groups=BLOOD_GROUPS)

@app.route("/recipient/match/<int:request_id>")
@login_required
@role_required("recipient")
def find_matches(request_id):
    conn=get_db()
    req=conn.execute("SELECT * FROM blood_requests WHERE id=? AND recipient_id=?",(request_id,session["user_id"])).fetchone()
    if not req:
        flash("Request not found.","danger"); return redirect(url_for("recipient_requests"))
    compatible=BLOOD_COMPATIBILITY.get(req["blood_group"],[])
    if compatible:
        placeholders=",".join("?"*len(compatible))
        donors=conn.execute(f"SELECT u.id,u.name,u.blood_group,u.phone,COUNT(d.id) as donation_count FROM users u LEFT JOIN donations d ON d.donor_id=u.id WHERE u.role='donor' AND u.blood_group IN ({placeholders}) GROUP BY u.id ORDER BY donation_count DESC",compatible).fetchall()
    else:
        donors=[]
    conn.close()
    return render_template("blood_match.html",request=req,donors=donors,compatible=compatible)

@app.route("/recipient/appointments", methods=["GET","POST"])
@login_required
@role_required("recipient")
def recipient_appointments():
    uid=session["user_id"]; conn=get_db()
    facilities=conn.execute("SELECT * FROM facilities").fetchall()
    if request.method == "POST":
        fid=request.form["facility_id"]; dt=request.form["appointment_date"]; tm=request.form["appointment_time"]; notes=request.form.get("notes","")
        if dt < date.today().isoformat():
            flash("Cannot book appointment in the past.","danger")
        else:
            conn.execute("INSERT INTO appointments (user_id,facility_id,appointment_date,appointment_time,type,notes) VALUES (?,?,?,?,?,?)",(uid,fid,dt,tm,"collection",notes))
            conn.commit(); flash("Appointment booked!","success")
            return redirect(url_for("recipient_appointments"))
    appointments=conn.execute("SELECT a.*,f.name as facility_name FROM appointments a JOIN facilities f ON a.facility_id=f.id WHERE a.user_id=? ORDER BY a.appointment_date DESC",(uid,)).fetchall()
    conn.close()
    return render_template("recipient_appointments.html",appointments=appointments,facilities=facilities,today=date.today().isoformat())

@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    rf=request.args.get("role","all"); conn=get_db()
    q="SELECT u.*,f.name as facility_name FROM users u LEFT JOIN facilities f ON u.facility_id=f.id"
    users=conn.execute(q+" WHERE u.role=? ORDER BY u.name",(rf,)).fetchall() if rf!="all" else conn.execute(q+" ORDER BY u.role,u.name").fetchall()
    conn.close()
    return render_template("admin_users.html",users=users,role_filter=rf)

@app.route("/admin/users/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def update_user(user_id):
    name=request.form["name"].strip(); email=request.form["email"].strip().lower(); role=request.form["role"]
    conn=get_db()
    conn.execute("UPDATE users SET name=?,email=?,role=? WHERE id=?",(name,email,role,user_id))
    conn.commit(); conn.close()
    flash("User updated successfully.","success")
    return redirect(url_for("admin_users"))

@app.route("/admin/requests", methods=["GET","POST"])
@login_required
@role_required("admin")
def admin_requests():
    conn=get_db()
    if request.method == "POST":
        conn.execute("UPDATE blood_requests SET status=?,matched_donor_id=? WHERE id=?",(request.form["status"],request.form.get("matched_donor_id") or None,request.form["request_id"]))
        conn.commit(); flash("Request updated.","success")
    requests_list=conn.execute("SELECT br.*,u.name as recipient_name,d.name as matched_donor_name,f.name as facility_name FROM blood_requests br JOIN users u ON br.recipient_id=u.id LEFT JOIN users d ON br.matched_donor_id=d.id LEFT JOIN facilities f ON br.facility_id=f.id ORDER BY CASE br.urgency WHEN 'critical' THEN 1 WHEN 'urgent' THEN 2 ELSE 3 END,br.created_at DESC").fetchall()
    donors=conn.execute("SELECT id,name,blood_group FROM users WHERE role='donor' ORDER BY name").fetchall()
    conn.close()
    return render_template("admin_requests.html",requests=requests_list,donors=donors)

@app.route("/admin/approve_request/<int:request_id>", methods=["POST"])
@login_required
@role_required("admin")
def approve_request(request_id):
    conn = get_db()
    conn.execute("UPDATE blood_requests SET status='approved' WHERE id=?", (request_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/admin/donations", methods=["GET","POST"])
@login_required
@role_required("admin")
def admin_donations():
    conn=get_db()
    if request.method == "POST":
        conn.execute("INSERT INTO donations (donor_id,facility_id,donation_date,blood_group,units,notes) VALUES (?,?,?,?,?,?)",(request.form["donor_id"],request.form["facility_id"],request.form["donation_date"],request.form["blood_group"],float(request.form.get("units",1.0)),request.form.get("notes","")))
        conn.commit(); flash("Donation record added.","success")
    donations=conn.execute("SELECT d.*,u.name as donor_name,f.name as facility_name FROM donations d JOIN users u ON d.donor_id=u.id LEFT JOIN facilities f ON d.facility_id=f.id ORDER BY d.donation_date DESC").fetchall()
    donors=conn.execute("SELECT id,name,blood_group FROM users WHERE role='donor' ORDER BY name").fetchall()
    facilities=conn.execute("SELECT * FROM facilities").fetchall()
    conn.close()
    return render_template("admin_donations.html",donations=donations,donors=donors,facilities=facilities,blood_groups=BLOOD_GROUPS,today=date.today().isoformat())

@app.route("/admin/appointments", methods=["GET","POST"])
@login_required
@role_required("admin")
def admin_appointments():
    conn=get_db()
    if request.method == "POST":
        conn.execute("UPDATE appointments SET status=? WHERE id=?",(request.form["status"],request.form["appointment_id"]))
        conn.commit(); flash("Appointment updated.","success")
    appointments=conn.execute("SELECT a.*,u.name as user_name,u.role as user_role,f.name as facility_name FROM appointments a JOIN users u ON a.user_id=u.id JOIN facilities f ON a.facility_id=f.id ORDER BY a.appointment_date DESC,a.appointment_time").fetchall()
    conn.close()
    return render_template("admin_appointments.html",appointments=appointments)

@app.route("/admin/complete_appointment/<int:appointment_id>", methods=["POST"])
@login_required
@role_required("admin")
def complete_appointment(appointment_id):
    conn = get_db()
    try:
        # Get appointment details with user info
        appointment = conn.execute("""
            SELECT a.*, u.blood_group, u.role
            FROM appointments a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = ?
        """, (appointment_id,)).fetchone()

        if not appointment:
            conn.close()
            return jsonify({"success": False, "error": "Appointment not found"}), 404

        # Update appointment status
        conn.execute("UPDATE appointments SET status='completed' WHERE id=?", (appointment_id,))

        # If it's a donation appointment and user has blood group, create a donation record
        if appointment['type'] == 'donation' and appointment['blood_group']:
            conn.execute("""
                INSERT INTO donations (donor_id, facility_id, donation_date, blood_group, units, status, notes)
                VALUES (?, ?, ?, ?, 1.0, 'completed', ?)
            """, (
                appointment['user_id'],
                appointment['facility_id'],
                appointment['appointment_date'],
                appointment['blood_group'],
                appointment['notes'] or f"Completed appointment on {appointment['appointment_date']}"
            ))

        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/admin/import-admins", methods=["GET","POST"])
@login_required
@role_required("admin")
def import_admins():
    conn=get_db(); facilities=conn.execute("SELECT * FROM facilities").fetchall(); conn.close()
    results=[]
    if request.method == "POST":
        file=request.files.get("csv_file")
        if not file or not file.filename.endswith(".csv"):
            flash("Please upload a valid CSV file.","danger")
        else:
            content=file.read().decode("utf-8"); reader=csv.DictReader(io.StringIO(content)); imported=0
            conn=get_db()
            for row in reader:
                try:
                    email=row.get("email","").strip().lower(); name=row.get("name","").strip()
                    if not email or not name: results.append({"row":row,"status":"Skipped (missing name/email)"}); continue
                    if conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone(): results.append({"row":row,"status":"Skipped (email exists)"}); continue
                    conn.execute("INSERT INTO users (name,email,password,phone,blood_group,role,facility_id) VALUES (?,?,?,?,?,?,?)",(name,email,generate_password_hash(row.get("password","admin123").strip()),row.get("phone","").strip(),row.get("blood_group","").strip(),"admin",row.get("facility_id","1").strip()))
                    imported+=1; results.append({"row":row,"status":"Imported ✓"})
                except Exception as e: results.append({"row":row,"status":f"Error: {e}"})
            conn.commit(); conn.close()
            flash(f"Imported {imported} admin accounts.","success")
    return render_template("import_admins.html",facilities=facilities,results=results)

def make_pdf_report(title, headers, rows, summary_lines=[]):
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,topMargin=0.75*inch,bottomMargin=0.75*inch)
    styles=getSampleStyleSheet()
    title_style=ParagraphStyle("t",parent=styles["Title"],textColor=colors.HexColor("#C0392B"),fontSize=20,spaceAfter=4)
    sub_style=ParagraphStyle("s",parent=styles["Normal"],textColor=colors.grey,fontSize=9,spaceAfter=14)
    elements=[
        Paragraph(f"🩸 Blood Bank — {title}",title_style),
        Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",sub_style),
        HRFlowable(width="100%",thickness=1,color=colors.HexColor("#C0392B")),
        Spacer(1,12),
        Table([headers]+rows,repeatRows=1,style=TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#C0392B")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,0),10),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#FEF9F9")]),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#DDDDDD")),
            ("FONTSIZE",(0,1),(-1,-1),9),
            ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ])),
    ]
    for s in summary_lines:
        elements.append(Spacer(1,8)); elements.append(Paragraph(s,styles["Normal"]))
    doc.build(elements); buf.seek(0); return buf

@app.route("/report/donors")
@login_required
@role_required("admin")
def report_donors():
    conn=get_db()
    donors=conn.execute("SELECT u.name,u.email,u.phone,u.blood_group,COUNT(d.id) as total,MAX(d.donation_date) as last FROM users u LEFT JOIN donations d ON d.donor_id=u.id WHERE u.role='donor' GROUP BY u.id ORDER BY u.name").fetchall()
    conn.close()
    headers=["Name","Email","Phone","Blood Group","Donations","Last Donation"]
    rows=[[d["name"],d["email"],d["phone"] or "—",d["blood_group"] or "—",str(d["total"]),d["last"] or "Never"] for d in donors]
    buf=make_pdf_report("Donor Report",headers,rows,[f"Total donors: {len(donors)}"])
    return send_file(buf,as_attachment=True,download_name=f"donor_report_{date.today()}.pdf",mimetype="application/pdf")

@app.route("/report/requests")
@login_required
@role_required("admin")
def report_requests():
    conn=get_db()
    reqs=conn.execute("SELECT u.name as recipient,br.blood_group,br.units,br.urgency,br.status,br.request_date,f.name as facility FROM blood_requests br JOIN users u ON br.recipient_id=u.id LEFT JOIN facilities f ON br.facility_id=f.id ORDER BY br.request_date DESC").fetchall()
    conn.close()
    headers=["Recipient","Blood Group","Units","Urgency","Status","Date","Facility"]
    rows=[[r["recipient"],r["blood_group"],str(r["units"]),r["urgency"].upper(),r["status"].upper(),r["request_date"],r["facility"] or "—"] for r in reqs]
    pending=sum(1 for r in reqs if r["status"]=="pending"); fulfilled=sum(1 for r in reqs if r["status"]=="fulfilled")
    buf=make_pdf_report("Blood Request Report",headers,rows,[f"Total: {len(reqs)} | Pending: {pending} | Fulfilled: {fulfilled}"])
    return send_file(buf,as_attachment=True,download_name=f"requests_report_{date.today()}.pdf",mimetype="application/pdf")

@app.route("/report/summary")
@login_required
@role_required("admin")
def report_summary():
    conn=get_db()
    stats={"donors":conn.execute("SELECT COUNT(*) FROM users WHERE role='donor'").fetchone()[0],"recipients":conn.execute("SELECT COUNT(*) FROM users WHERE role='recipient'").fetchone()[0],"donations":conn.execute("SELECT COUNT(*) FROM donations").fetchone()[0],"requests":conn.execute("SELECT COUNT(*) FROM blood_requests").fetchone()[0],"pending":conn.execute("SELECT COUNT(*) FROM blood_requests WHERE status='pending'").fetchone()[0],"fulfilled":conn.execute("SELECT COUNT(*) FROM blood_requests WHERE status='fulfilled'").fetchone()[0]}
    blood_dist=conn.execute("SELECT blood_group,COUNT(*) as cnt FROM users WHERE role='donor' AND blood_group!='' GROUP BY blood_group").fetchall()
    conn.close()
    headers=["Metric","Value"]
    rows=[["Total Donors",str(stats["donors"])],["Total Recipients",str(stats["recipients"])],["Total Donations",str(stats["donations"])],["Total Requests",str(stats["requests"])],["Pending Requests",str(stats["pending"])],["Fulfilled Requests",str(stats["fulfilled"])]]
    buf=make_pdf_report("System Summary Report",headers,rows,["Blood Group Distribution: "+", ".join(f"{b['blood_group']}: {b['cnt']}" for b in blood_dist)])
    return send_file(buf,as_attachment=True,download_name=f"summary_report_{date.today()}.pdf",mimetype="application/pdf")

@app.route("/api/chart-data")
@login_required
@role_required("admin")
def chart_data():
    conn=get_db()
    bd=conn.execute("SELECT blood_group,COUNT(*) as cnt FROM users WHERE role='donor' AND blood_group!='' GROUP BY blood_group ORDER BY blood_group").fetchall()
    mn=conn.execute("SELECT strftime('%Y-%m',donation_date) as month,COUNT(*) as cnt FROM donations GROUP BY month ORDER BY month ASC LIMIT 6").fetchall()
    rs=conn.execute("SELECT status,COUNT(*) as cnt FROM blood_requests GROUP BY status").fetchall()
    conn.close()
    return jsonify({"blood_dist":{"labels":[r["blood_group"] for r in bd],"data":[r["cnt"] for r in bd]},"monthly":{"labels":[r["month"] for r in mn],"data":[r["cnt"] for r in mn]},"request_status":{"labels":[r["status"] for r in rs],"data":[r["cnt"] for r in rs]}})

if __name__=="__main__":
    app.run(debug=True,port=5000)
