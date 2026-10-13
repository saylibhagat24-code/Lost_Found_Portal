from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

import mysql.connector
import os
import uuid

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename


app = Flask(__name__)


# ==========================================
# FLASK CONFIGURATION
# ==========================================

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-only-change-this-secret"
)

# Photo upload configuration
app.config["UPLOAD_FOLDER"] = "static/uploads"

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


# ==========================================
# ALLOWED FILE FUNCTION
# ==========================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ==========================================
# MYSQL CONNECTION
# ==========================================

def get_db_connection():

    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="lost_and_found"
    )


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    return render_template("index.html")


# ==========================================
# REGISTRATION
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        phone = request.form.get(
            "phone", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if not name or not email or not password:

            return "Please fill in all required fields."

        hashed_password = generate_password_hash(
            password
        )

        db = get_db_connection()
        cursor = db.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO users
                (name, email, phone, password)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    name,
                    email,
                    phone,
                    hashed_password
                )
            )

            db.commit()

        except mysql.connector.IntegrityError:

            db.rollback()

            return "This email is already registered."

        finally:

            cursor.close()
            db.close()

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        db = get_db_connection()

        cursor = db.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT id, name, email, password
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]

            session["user_name"] = user["name"]

            session["user_email"] = user["email"]

            return redirect(
                url_for("dashboard")
            )

        return "Invalid email or password."

    return render_template(
        "login.html"
    )


# ==========================================
# DASHBOARD
# ==========================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    user_name = session["user_name"]

    db = get_db_connection()

    cursor = db.cursor(
        dictionary=True
    )

    # Total Reports
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM reports
        WHERE user_id = %s
        """,
        (user_id,)
    )

    total_reports = cursor.fetchone()["total"]

    # Lost Items
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM reports
        WHERE user_id = %s
        AND report_type = 'Lost'
        """,
        (user_id,)
    )

    lost_items = cursor.fetchone()["total"]

    # Found Items
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM reports
        WHERE user_id = %s
        AND report_type = 'Found'
        """,
        (user_id,)
    )

    found_items = cursor.fetchone()["total"]

    # Resolved Items
    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM reports
        WHERE user_id = %s
        AND status = 'Resolved'
        """,
        (user_id,)
    )

    resolved_items = cursor.fetchone()["total"]

    # Recent Reports
    cursor.execute(
        """
        SELECT
            item_name,
            report_type,
            report_date,
            status,
            photo
        FROM reports
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (user_id,)
    )

    recent_reports = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",

        user_name=user_name,

        total_reports=total_reports,

        lost_items=lost_items,

        found_items=found_items,

        resolved_items=resolved_items,

        recent_reports=recent_reports
    )


# ==========================================
# REPORT LOST ITEM
# ==========================================

@app.route(
    "/report-lost",
    methods=["GET", "POST"]
)
def report_lost():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if request.method == "POST":

        user_id = session["user_id"]

        item_name = request.form.get(
            "item_name", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        location = request.form.get(
            "location", ""
        ).strip()

        report_date = request.form.get(
            "report_date", ""
        )

        photo = request.files.get(
            "photo"
        )

        # Validate required fields
        if not item_name or not description or not location or not report_date:

            return "Please fill in all required fields."

        photo_filename = None

        # ==================================
        # PHOTO UPLOAD
        # ==================================

        if photo and photo.filename:

            if not allowed_file(
                photo.filename
            ):

                return (
                    "Invalid photo format. "
                    "Use JPG, PNG, JPEG, or WEBP."
                )

            original_filename = secure_filename(
                photo.filename
            )

            extension = original_filename.rsplit(
                ".",
                1
            )[1].lower()

            unique_filename = (
                str(uuid.uuid4())
                + "."
                + extension
            )

            photo_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                unique_filename
            )

            photo.save(photo_path)

            photo_filename = unique_filename

        # ==================================
        # INSERT REPORT INTO DATABASE
        # ==================================

        db = get_db_connection()

        cursor = db.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO reports
                (
                    user_id,
                    item_name,
                    report_type,
                    description,
                    location,
                    report_date,
                    status,
                    photo
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    user_id,
                    item_name,
                    "Lost",
                    description,
                    location,
                    report_date,
                    "Pending",
                    photo_filename
                )
            )

            db.commit()

        except mysql.connector.Error as error:

            db.rollback()

            return f"Database error: {error}"

        finally:

            cursor.close()
            db.close()

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "report-lost.html"
    )
# ==========================================
# REPORT FOUND ITEM
# ==========================================

@app.route("/report-found", methods=["GET", "POST"])
def report_found():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        user_id = session["user_id"]

        item_name = request.form.get("item_name", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        report_date = request.form.get("report_date", "")

        photo = request.files.get("photo")

        # Validate required fields
        if not item_name or not description or not location or not report_date:
            return "Please fill in all required fields."

        photo_filename = None

        # Photo upload
        if photo and photo.filename:

            if not allowed_file(photo.filename):
                return "Invalid photo format. Use JPG, PNG, JPEG, or WEBP."

            original_filename = secure_filename(photo.filename)

            extension = original_filename.rsplit(".", 1)[1].lower()

            unique_filename = str(uuid.uuid4()) + "." + extension

            photo_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                unique_filename
            )

            photo.save(photo_path)

            photo_filename = unique_filename

        # Insert found report
        db = get_db_connection()
        cursor = db.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO reports
                (
                    user_id,
                    item_name,
                    report_type,
                    description,
                    location,
                    report_date,
                    status,
                    photo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    item_name,
                    "Found",
                    description,
                    location,
                    report_date,
                    "Pending",
                    photo_filename
                )
            )

            db.commit()

        except mysql.connector.Error as error:

            db.rollback()
            return f"Database error: {error}"

        finally:

            cursor.close()
            db.close()

        return redirect(url_for("dashboard"))

    return render_template("report-found.html")

# ==========================================
# SEARCH LOST AND FOUND ITEMS
# ==========================================

@app.route("/search")
def search_items():

    if "user_id" not in session:
        return redirect(url_for("login"))

    item_name = request.args.get(
        "item_name",
        ""
    ).strip()

    location = request.args.get(
        "location",
        ""
    ).strip()

    report_type = request.args.get(
        "report_type",
        ""
    ).strip()


    db = get_db_connection()

    cursor = db.cursor(dictionary=True)


    query = """
        SELECT
            id,
            item_name,
            report_type,
            description,
            location,
            report_date,
            status,
            photo

        FROM reports

        WHERE 1 = 1
    """

    values = []


    # Search by item name
    if item_name:

        query += """
            AND item_name LIKE %s
        """

        values.append(
            "%" + item_name + "%"
        )


    # Search by location
    if location:

        query += """
            AND location LIKE %s
        """

        values.append(
            "%" + location + "%"
        )


    # Filter by report type
    if report_type in ["Lost", "Found"]:

        query += """
            AND report_type = %s
        """

        values.append(
            report_type
        )


    query += """
        ORDER BY created_at DESC
    """


    cursor.execute(
        query,
        tuple(values)
    )


    reports = cursor.fetchall()


    cursor.close()
    db.close()


    return render_template(
        "search.html",
        reports=reports
    )
# ==========================================
# ITEM DETAILS
# ==========================================

@app.route("/item-details/<int:report_id>")
def item_details(report_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db_connection()

    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                item_name,
                report_type,
                description,
                location,
                report_date,
                status,
                photo,
                created_at
            FROM reports
            WHERE id = %s
            """,
            (report_id,)
        )

        report = cursor.fetchone()

    finally:

        cursor.close()
        db.close()

    if report is None:
        return "Report not found", 404

    return render_template(
        "item-details.html",
        report=report
    )
# ==========================================
# USER PROFILE
# ==========================================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, name, email, phone
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],)
    )

    user = cursor.fetchone()

    cursor.close()
    db.close()

    if user is None:
        return "User not found", 404

    return render_template(
        "profile.html",
        user=user
    )


# ==========================================
# EDIT PROFILE
# ==========================================

@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()

        if not name or not email:
            cursor.close()
            db.close()
            return "Name and email are required."

        try:

            cursor.execute(
                """
                UPDATE users
                SET name = %s, email = %s, phone = %s
                WHERE id = %s
                """,
                (
                    name,
                    email,
                    phone,
                    session["user_id"]
                )
            )

            db.commit()

            session["user_name"] = name
            session["user_email"] = email

        except mysql.connector.IntegrityError:

            db.rollback()

            cursor.close()
            db.close()

            return "This email is already registered."

        finally:

            if not cursor.is_closed():
                cursor.close()

            if db.is_connected():
                db.close()

        return redirect(url_for("profile"))

    cursor.execute(
        """
        SELECT id, name, email, phone
        FROM users
        WHERE id = %s
        """,
        (session["user_id"],)
    )

    user = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template(
        "edit-profile.html",
        user=user
    )

# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
