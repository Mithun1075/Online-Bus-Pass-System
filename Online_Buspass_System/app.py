from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import random
import string
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret_key"

DB_REGISTER = "register.db"
DB_APPLICANT = "applicant.db"


# Database

def init_register_db():
    conn = sqlite3.connect(DB_REGISTER)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS registered_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def init_applicant_db():
    conn = sqlite3.connect(DB_APPLICANT)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS applicants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pass_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            dob TEXT NOT NULL,
            gender TEXT NOT NULL,
            email TEXT,
            location TEXT NOT NULL,
            pass_type TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# helpers

def generate_pass_id():
    return "EBP-" + "".join(random.choices(string.digits, k=5))


def fetch_pass(pass_id):
    conn = sqlite3.connect(DB_APPLICANT)
    c = conn.cursor()
    c.execute("""
        SELECT pass_id, name, gender, location, pass_type
        FROM applicants WHERE pass_id = ?
    """, (pass_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    amount = 300 if row[4] == "student" else 1000

    return {
        "pass_id": row[0],
        "name": row[1],
        "gender": row[2],
        "location": row[3],
        "pass_type": row[4],
        "amount": amount,
        "expiry_date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    }


def login_required():
    return "user_id" in session


# routes

@app.route("/")
@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("login-email")
    password = request.form.get("login-password")

    conn = sqlite3.connect(DB_REGISTER)
    c = conn.cursor()
    c.execute("SELECT id, password FROM registered_users WHERE username=?", (email,))
    user = c.fetchone()
    conn.close()

    if user and check_password_hash(user[1], password):
        session["user_id"] = user[0]
        return redirect(url_for("dashboard"))

    flash("Invalid login credentials")
    return redirect(url_for("login_page"))


@app.route("/register", methods=["POST"])
def register():
    email = request.form.get("register-email")
    password = generate_password_hash(request.form.get("register-password"))

    conn = sqlite3.connect(DB_REGISTER)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO registered_users (username, password) VALUES (?, ?)",
            (email, password)
        )
        conn.commit()
        flash("Registration successful")
    except sqlite3.IntegrityError:
        flash("User already exists")
    conn.close()

    return redirect(url_for("login_page"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login_page"))
    return render_template("dashboard.html")


@app.route("/application")
def application():
    if not login_required():
        return redirect(url_for("login_page"))
    return render_template("application.html")


@app.route("/new-application", methods=["POST"])
def new_application():
    if not login_required():
        return redirect(url_for("login_page"))

    pass_type = request.form.get("pass_type")
    location = request.form.get("location")

    if not pass_type or not location:
        flash("All fields are required")
        return redirect(url_for("application"))

    pass_id = generate_pass_id()

    conn = sqlite3.connect(DB_APPLICANT)
    c = conn.cursor()
    c.execute("""
        INSERT INTO applicants
        (pass_id, name, age, dob, gender, email, location, pass_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pass_id,
        request.form.get("name"),
        request.form.get("age"),
        request.form.get("dob"),
        request.form.get("gender"),
        request.form.get("email"),
        location,
        pass_type
    ))
    conn.commit()
    conn.close()

    return redirect(url_for("submission", pass_id=pass_id))


# renew pass

@app.route("/renewal", methods=["GET", "POST"])
def renewal():
    if not login_required():
        return redirect(url_for("login_page"))

    if request.method == "POST":
        pass_id = request.form.get("pass_id")

        if not fetch_pass(pass_id):
            flash("Invalid Pass ID")
            return redirect(url_for("renewal"))

        return redirect(url_for("payment", pass_id=pass_id))

    return render_template("renewal.html")


# View E-pass from dashboard

@app.route("/view-epass", methods=["POST"])
def view_epass():
    if not login_required():
        return redirect(url_for("login_page"))

    pass_id = request.form.get("pass_id")

    if not fetch_pass(pass_id):
        flash("Invalid Pass ID")
        return redirect(url_for("dashboard"))

    return redirect(url_for("generate_pass", pass_id=pass_id))


@app.route("/submission/<pass_id>")
def submission(pass_id):
    if not login_required():
        return redirect(url_for("login_page"))
    return render_template("submission.html", pass_id=pass_id)


@app.route("/payment/<pass_id>", methods=["GET", "POST"])
def payment(pass_id):
    if not login_required():
        return redirect(url_for("login_page"))

    details = fetch_pass(pass_id)
    if not details:
        return "Pass not found"

    if request.method == "POST":
        return redirect(url_for("generate_pass", pass_id=pass_id))

    return render_template(
        "payment.html",
        pass_id=pass_id,
        amount=details["amount"]
    )


@app.route("/generate-pass/<pass_id>")
def generate_pass(pass_id):
    if not login_required():
        return redirect(url_for("login_page"))

    details = fetch_pass(pass_id)
    if not details:
        return "Pass not found"

    return render_template("e_pass.html", pass_details=details)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


if __name__ == "__main__":
    init_register_db()
    init_applicant_db()
    app.run(debug=True)
