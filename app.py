


from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
import json
import os
import sqlite3

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)

from werkzeug.security import check_password_hash, generate_password_hash

from transaction import Transaction
from transaction_repository import SQLiteTransactionRepository
from dashboard import get_financial_summary
from user import create_user


# -----------------------------------------------
# APPLICATION CONFIGURATION
# -----------------------------------------------
app = Flask(__name__)

secret_key = os.environ.get("SECRET_KEY")

if not secret_key:
    raise RuntimeError(
        "SECRET_KEY is missing. Set it before running OrgFinance."
    )

app.config["SECRET_KEY"] = secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

# Use the database located beside this app.py file.
DATABASE_NAME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "orgfinance.db",
)

repository = SQLiteTransactionRepository(DATABASE_NAME)


# -----------------------------------------------
# FINANCE OFFICER BUDGET TABLES
# These tables are separate from the existing transaction history.
# -----------------------------------------------
def ensure_finance_tables():
    """Create finance tables using the existing budget repository schema."""
    connection = sqlite3.connect(DATABASE_NAME)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_name TEXT NOT NULL,
                planned_amount REAL NOT NULL CHECK (planned_amount >= 0),
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                budget_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                expense_date TEXT NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'Unpaid'
                    CHECK (payment_status IN ('Paid', 'Unpaid')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE RESTRICT
            )
        """)
        connection.commit()
    finally:
        connection.close()

def valid_positive_amount(value):
    """Return a positive two-decimal-place amount, or None if invalid."""
    try:
        amount = Decimal(str(value).strip())
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
            return None
        return amount
    except (InvalidOperation, ValueError, TypeError):
        return None


ensure_finance_tables()

# These are assigned account roles, not interface modes.
VALID_ROLES = {
    "head_admin",
    "assistant_admin",
    "supervisor",
    "finance_officer",
    "member",
}

AUDIT_ROLES = {
    "head_admin",
    "assistant_admin",
    "supervisor",
}


# -----------------------------------------------
# AUDIT LOG
# -----------------------------------------------
def ensure_audit_table():
    """Create the audit table if it does not exist."""
    connection = sqlite3.connect(DATABASE_NAME)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS transaction_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                changed_by_id INTEGER NOT NULL,
                changed_by_username TEXT NOT NULL,
                old_values TEXT NOT NULL,
                new_values TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
    finally:
        connection.close()


def transaction_snapshot(record):
    """Convert a transaction row into a before/after snapshot."""
    return {
        "transaction_type": record[1],
        "amount": str(record[2]),
        "description": record[3],
        "category": record[4],
        "transaction_date": record[5],
    }


def insert_audit_record(
    connection,
    transaction_id,
    action,
    old_values,
    new_values,
):
    """Insert an audit entry using the current database transaction."""
    connection.execute("""
        INSERT INTO transaction_audit (
            transaction_id,
            action,
            changed_by_id,
            changed_by_username,
            old_values,
            new_values
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        transaction_id,
        action,
        session["user_id"],
        session["username"],
        json.dumps(old_values, ensure_ascii=False),
        json.dumps(new_values, ensure_ascii=False),
    ))


# -----------------------------------------------
# USER DATABASE
# -----------------------------------------------
def get_user_by_username(username):
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row

    try:
        return connection.execute("""
            SELECT id, username, password_hash, role, is_active
            FROM users
            WHERE username = ?
        """, (username,)).fetchone()
    finally:
        connection.close()


# -----------------------------------------------
# ADMIN ANALYTICS AND VISIT TRACKING
# -----------------------------------------------
def ensure_analytics_tables():
    """Create the page-visit table if it does not exist."""
    connection = sqlite3.connect(DATABASE_NAME)
    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS page_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()
    finally:
        connection.close()


def get_admin_analytics():
    """Return registration totals and daily page views for the charts."""
    ensure_analytics_tables()
    connection = sqlite3.connect(DATABASE_NAME)
    try:
        registrations = connection.execute("""
            SELECT role, COUNT(*)
            FROM users
            GROUP BY role
            ORDER BY role
        """).fetchall()

        # Show the most recent seven calendar days, including zero-visit days.
        rows = connection.execute("""
            SELECT date(visited_at), COUNT(*)
            FROM page_visits
            WHERE date(visited_at) >= date('now', '-6 days')
            GROUP BY date(visited_at)
            ORDER BY date(visited_at)
        """).fetchall()
    finally:
        connection.close()

    visits_by_day = {day: count for day, count in rows}
    dates = [(date.today() - timedelta(days=offset)).isoformat()
             for offset in range(6, -1, -1)]
    return {
        "registration_labels": [role.replace("_", " ").title() for role, _ in registrations],
        "registration_values": [count for _, count in registrations],
        "visit_labels": dates,
        "visit_values": [visits_by_day.get(day, 0) for day in dates],
        "registered_total": sum(count for _, count in registrations),
        "visit_total": sum(visits_by_day.values()),
    }


@app.before_request
def record_page_visit():
    """Count page requests (not unique people); skip static assets."""
    if request.endpoint == "static":
        return
    try:
        ensure_analytics_tables()
        connection = sqlite3.connect(DATABASE_NAME)
        try:
            connection.execute("INSERT INTO page_visits DEFAULT VALUES")
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error:
        # Analytics should not prevent the finance application from loading.
        app.logger.exception("Could not record page visit.")


# -----------------------------------------------
# LOGIN REQUIRED
# -----------------------------------------------
def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return wrapped_view


# -----------------------------------------------
# ROLE-BASED ACCESS CONTROL
# -----------------------------------------------
def get_current_user():
    """Build the appropriate OOP User object from the authenticated session."""
    role = session.get("role")
    if not role:
        return None
    try:
        return create_user(
            role,
            user_id=session.get("user_id"),
            username=session.get("username", ""),
        )
    except ValueError:
        return None


def role_required(*allowed_roles):
    """Restrict a route using the role-specific User object."""
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))

            current_user = get_current_user()
            if current_user is None or not current_user.can_access_role_route(allowed_roles):
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


def permission_required(permission):
    """Authorize an action through polymorphic role permissions."""
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))

            current_user = get_current_user()
            if current_user is None or not current_user.has_permission(permission):
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


# -----------------------------------------------
# LOGIN
# -----------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

        if (
            user
            and user["is_active"] == 1
            and user["role"] in VALID_ROLES
            and check_password_hash(user["password_hash"], password)
        ):
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            # Interface mode does not change assigned permissions.
            if user["role"] in ("head_admin", "assistant_admin"):
                session["active_mode"] = "admin"
            elif user["role"] == "supervisor":
                session["active_mode"] = "supervisor"
            else:
                session["active_mode"] = "standard"

            flash("Login successful.", "success")
            return redirect(url_for("home"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


# -----------------------------------------------
# SWITCH INTERFACE MODE
# -----------------------------------------------
@app.route("/switch-mode", methods=["POST"])
@login_required
def switch_mode():
    role = session.get("role")
    current_mode = session.get("active_mode", "standard")

    # Interface mode changes the presentation only. It never changes
    # the user's assigned role or grants additional permissions.
    if role in ("head_admin", "assistant_admin"):
        session["active_mode"] = (
            "supervisor" if current_mode == "admin" else "admin"
        )
    elif role == "supervisor":
        session["active_mode"] = (
            "admin" if current_mode == "supervisor" else "supervisor"
        )
    else:
        abort(403)

    session.modified = True
    flash(
        f"Interface mode changed to "
        f"{session['active_mode'].replace('_', ' ').title()}.",
        "success",
    )
    return redirect(url_for("home"))


# -----------------------------------------------
# LOGOUT
# -----------------------------------------------
@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have logged out.", "success")
    return redirect(url_for("login"))


# -----------------------------------------------
# FORBIDDEN ACCESS PAGE
# -----------------------------------------------
@app.errorhandler(403)
def forbidden(error):
    return render_template("403.html"), 403


# -----------------------------------------------
# FINANCIAL DASHBOARD
# All logged-in roles can view.
# -----------------------------------------------
@app.route("/")
@login_required
def home():
    role = session.get("role")
    active_mode = session.get("active_mode", "standard")

    # Finance Officers use their dedicated budget and expense dashboard.
    if role == "finance_officer":
        return redirect(url_for("finance_officer_dashboard"))

    # Admin accounts can open their assigned admin dashboards.
    # A Supervisor can switch the interface-mode label, but this never grants
    # admin permissions; Supervisors always land on the Supervisor dashboard.
    if role == "supervisor":
        return redirect(url_for("supervisor_dashboard"))
    if active_mode == "admin" and role == "head_admin":
        return redirect(url_for("head_admin_dashboard"))
    if active_mode == "admin" and role == "assistant_admin":
        return redirect(url_for("assistant_admin_dashboard"))

    income, expenses, cash = get_financial_summary(repository)
    return render_template(
        "dashboard.html",
        income=f"{income:,.2f}",
        expenses=f"{expenses:,.2f}",
        cash=f"{cash:,.2f}",
        role=role,
        active_mode=active_mode,
    )


# -----------------------------------------------
# ROLE-SPECIFIC ADMIN DASHBOARDS
# -----------------------------------------------
@app.route("/admin/head")
@role_required("head_admin")
def head_admin_dashboard():
    analytics = get_admin_analytics()
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    try:
        assistants = connection.execute("""
            SELECT id, username, is_active
            FROM users
            WHERE role = 'assistant_admin'
            ORDER BY username COLLATE NOCASE
        """).fetchall()
    finally:
        connection.close()
    return render_template(
        "head_admin_dashboard.html",
        analytics=analytics,
        assistants=assistants,
        role=session.get("role"),
        active_mode=session.get("active_mode", "admin"),
    )


@app.route("/admin/assistant")
@role_required("assistant_admin")
def assistant_admin_dashboard():
    return render_template(
        "assistant_admin_dashboard.html",
        analytics=get_admin_analytics(),
        role=session.get("role"),
        active_mode=session.get("active_mode", "admin"),
    )


# -----------------------------------------------
# CREATE ADMIN AND STAFF ACCOUNTS
# Head Admin: Head Admin, Assistant Admin, Finance Officer, Member.
# Assistant Admin: Assistant Admin only.
# -----------------------------------------------
@app.route("/admin/users/create", methods=["POST"])
@role_required("head_admin", "assistant_admin")
def create_admin_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    requested_role = request.form.get(
        "role", "assistant_admin"
    ).strip().lower()
    current_role = session.get("role")

    if current_role == "head_admin":
        allowed_new_roles = {
            "head_admin",
            "assistant_admin",
            "finance_officer",
            "member",
        }
    elif current_role == "assistant_admin":
        allowed_new_roles = {"assistant_admin"}
    else:
        abort(403)

    if requested_role not in allowed_new_roles:
        abort(403)

    if len(username) < 3 or len(username) > 50:
        flash("Username must be between 3 and 50 characters.", "error")
        return redirect(url_for(
            "head_admin_dashboard" if current_role == "head_admin"
            else "assistant_admin_dashboard"
        ))

    if len(password) < 8:
        flash("Password must contain at least 8 characters.", "error")
        return redirect(url_for(
            "head_admin_dashboard" if current_role == "head_admin"
            else "assistant_admin_dashboard"
        ))

    connection = sqlite3.connect(DATABASE_NAME)
    try:
        existing = connection.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            flash("That username is already in use.", "error")
            return redirect(url_for(
                "head_admin_dashboard" if current_role == "head_admin"
                else "assistant_admin_dashboard"
            ))

        connection.execute("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES (?, ?, ?, 1)
        """, (username, generate_password_hash(password), requested_role))
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Account creation failed.")
        flash("Could not create the account. Check the users table schema.", "error")
        return redirect(url_for(
            "head_admin_dashboard" if current_role == "head_admin"
            else "assistant_admin_dashboard"
        ))
    finally:
        connection.close()

    role_name = requested_role.replace("_", " ").title()
    flash(f"{role_name} account created successfully.", "success")
    return redirect(url_for(
        "head_admin_dashboard" if current_role == "head_admin"
        else "assistant_admin_dashboard"
    ))


# -----------------------------------------------
# REMOVE ASSISTANT ADMIN (HEAD ADMIN ONLY)
# Soft-disable the account so audit history is retained.
# -----------------------------------------------
@app.route("/admin/assistants/<int:user_id>/remove", methods=["POST"])
@role_required("head_admin")
def remove_assistant_admin(user_id):
    connection = sqlite3.connect(DATABASE_NAME)
    try:
        cursor = connection.execute("""
            UPDATE users
            SET is_active = 0
            WHERE id = ? AND role = 'assistant_admin' AND is_active = 1
        """, (user_id,))
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Assistant Admin removal failed.")
        flash("Could not remove this Assistant Admin.", "error")
        return redirect(url_for("home"))
    finally:
        connection.close()

    if cursor.rowcount:
        flash("Assistant Admin account deactivated.", "success")
    else:
        flash("Active Assistant Admin not found.", "error")
    return redirect(url_for("home"))


# -----------------------------------------------
# ADD INCOME OR EXPENSE
# Finance Officer only.
# -----------------------------------------------
@app.route("/transactions/new", methods=["GET", "POST"])
@permission_required("create_transaction")
def add_transaction():
    if request.method == "POST":
        transaction_type = request.form.get(
            "transaction_type", ""
        ).strip()
        amount_text = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        transaction_date = request.form.get(
            "transaction_date", ""
        ).strip()

        try:
            amount = Decimal(amount_text)

            if not amount.is_finite() or amount <= 0:
                raise ValueError("Amount must be greater than zero.")

            if max(0, -amount.as_tuple().exponent) > 2:
                raise ValueError(
                    "Use no more than two decimal places."
                )

            if transaction_type not in ("Income", "Expense"):
                raise ValueError("Choose Income or Expense.")

            if not description or not category:
                raise ValueError(
                    "Description and category are required."
                )

            if len(description) > 200 or len(category) > 100:
                raise ValueError(
                    "Description or category is too long."
                )

            parsed_date = date.fromisoformat(transaction_date)

            transaction = Transaction(
                transaction_type,
                float(amount),
                description,
                category,
                parsed_date.isoformat(),
            )

            repository.add(transaction)

            flash("Transaction saved successfully!", "success")
            return redirect(url_for("home"))

        except (InvalidOperation, ValueError) as error:
            flash(f"Please check your entry: {error}", "error")

    return render_template("transactions.html")


# -----------------------------------------------
# TRANSACTION HISTORY
# All logged-in roles can view.
# -----------------------------------------------
@app.route("/transactions")
@login_required
def transaction_history():
    transactions = repository.get_all()

    return render_template(
        "history.html",
        transactions=transactions,
    )


# -----------------------------------------------
# EDIT TRANSACTION
# Finance Officer only.
# Save the edit and its audit entry together.
# -----------------------------------------------
@app.route(
    "/transactions/<int:transaction_id>/edit",
    methods=["GET", "POST"],
)
@permission_required("edit_transaction")
def edit_transaction(transaction_id):
    record = repository.get_by_id(transaction_id)

    if record is None:
        flash("Transaction not found.", "error")
        return redirect(url_for("transaction_history"))

    if request.method == "POST":
        transaction_type = request.form.get(
            "transaction_type", ""
        ).strip()
        amount_text = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        transaction_date = request.form.get(
            "transaction_date", ""
        ).strip()

        try:
            amount = Decimal(amount_text)

            if not amount.is_finite() or amount <= 0:
                raise ValueError("Amount must be greater than zero.")

            if max(0, -amount.as_tuple().exponent) > 2:
                raise ValueError(
                    "Use no more than two decimal places."
                )

            if transaction_type not in ("Income", "Expense"):
                raise ValueError("Choose Income or Expense.")

            if not description or not category:
                raise ValueError(
                    "Description and category are required."
                )

            if len(description) > 200 or len(category) > 100:
                raise ValueError(
                    "Description or category is too long."
                )

            parsed_date = date.fromisoformat(transaction_date)

            old_values = transaction_snapshot(record)
            new_values = {
                "transaction_type": transaction_type,
                "amount": str(amount),
                "description": description,
                "category": category,
                "transaction_date": parsed_date.isoformat(),
            }

            # Ensure the audit table exists before starting the
            # transaction that updates the financial record.
            ensure_audit_table()

            connection = sqlite3.connect(DATABASE_NAME)

            try:
                connection.execute("BEGIN")

                cursor = connection.execute("""
                    UPDATE transactions
                    SET transaction_type = ?,
                        amount = ?,
                        description = ?,
                        category = ?,
                        transaction_date = ?
                    WHERE id = ?
                """, (
                    transaction_type,
                    float(amount),
                    description,
                    category,
                    parsed_date.isoformat(),
                    transaction_id,
                ))

                if cursor.rowcount == 0:
                    connection.rollback()
                    flash("Transaction was not updated.", "error")
                    return redirect(url_for("transaction_history"))

                insert_audit_record(
                    connection,
                    transaction_id,
                    "EDIT",
                    old_values,
                    new_values,
                )

                connection.commit()

            except sqlite3.Error:
                connection.rollback()
                raise

            finally:
                connection.close()

            flash(
                "Transaction updated and audit entry recorded.",
                "success",
            )
            return redirect(url_for("transaction_history"))

        except (InvalidOperation, ValueError) as error:
            flash(f"Please check your entry: {error}", "error")
        except sqlite3.Error:
            app.logger.exception("Transaction edit failed.")
            flash(
                "The update could not be saved. "
                "Please try again.",
                "error",
            )

    return render_template(
        "edit_transaction.html",
        transaction=record,
    )


# -----------------------------------------------
# DELETE TRANSACTION
# Supervisor only.
# Preserve a deletion record in the audit log.
# -----------------------------------------------
@app.route(
    "/transactions/<int:transaction_id>/delete",
    methods=["POST"],
)
@permission_required("delete_transaction")
def delete_transaction(transaction_id):
    ensure_audit_table()
    connection = sqlite3.connect(DATABASE_NAME)

    try:
        connection.execute("BEGIN")

        record = connection.execute("""
            SELECT id, transaction_type, amount,
                   description, category, transaction_date
            FROM transactions
            WHERE id = ?
        """, (transaction_id,)).fetchone()

        if record is None:
            connection.rollback()
            flash("Transaction not found.", "error")
            return redirect(url_for("transaction_history"))

        old_values = transaction_snapshot(record)

        cursor = connection.execute(
            "DELETE FROM transactions WHERE id = ?",
            (transaction_id,),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            flash("Transaction not found.", "error")
            return redirect(url_for("transaction_history"))

        insert_audit_record(
            connection,
            transaction_id,
            "DELETE",
            old_values,
            {"deleted": True},
        )

        connection.commit()
        flash(
            "Transaction deleted and deletion recorded in the audit log.",
            "success",
        )

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Transaction deletion failed.")
        flash(
            "The transaction could not be deleted. Please try again.",
            "error",
        )

    finally:
        connection.close()

    return redirect(url_for("transaction_history"))


# -----------------------------------------------
# AUDIT LOG
# Head Admin, Assistant Admin, and Supervisor.
# -----------------------------------------------
@app.route("/audit-log")
@role_required(*AUDIT_ROLES)
def audit_log():
    ensure_audit_table()
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row

    try:
        audit_records = connection.execute("""
            SELECT
                id,
                transaction_id,
                action,
                changed_by_username,
                old_values,
                new_values,
                changed_at
            FROM transaction_audit
            ORDER BY id DESC
        """).fetchall()
    finally:
        connection.close()

    audit_entries = []

    for row in audit_records:
        entry = dict(row)
        entry["old_values"] = json.loads(entry["old_values"])
        entry["new_values"] = json.loads(entry["new_values"])
        audit_entries.append(entry)

    return render_template(
        "audit_log.html",
        audit_entries=audit_entries,
    )




# -----------------------------------------------
# SUPERVISOR DASHBOARD
# Supervisor can review financial records, deletion history,
# and before/after changes recorded in the audit log.
# -----------------------------------------------
@app.route("/supervisor")
@role_required("supervisor")
def supervisor_dashboard():
    income, expenses, cash = get_financial_summary(repository)
    ensure_audit_table()

    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    try:
        audit_records = connection.execute("""
            SELECT
                id,
                transaction_id,
                action,
                changed_by_username,
                old_values,
                new_values,
                changed_at
            FROM transaction_audit
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()
    finally:
        connection.close()

    audit_entries = []
    for row in audit_records:
        entry = dict(row)
        try:
            entry["old_values"] = json.loads(entry["old_values"])
            entry["new_values"] = json.loads(entry["new_values"])
        except (TypeError, json.JSONDecodeError):
            entry["old_values"] = {}
            entry["new_values"] = {}
        audit_entries.append(entry)

    # This chart treats recorded income as available funds. It does not
    # represent a separate planned-budget table unless one is added later.
    remaining = max(float(cash), 0.0)
    used = max(float(expenses), 0.0)
    return render_template(
        "supervisor_dashboard.html",
        income=f"{income:,.2f}",
        expenses=f"{expenses:,.2f}",
        cash=f"{cash:,.2f}",
        chart_used=used,
        chart_remaining=remaining,
        transactions=repository.get_all(),
        audit_entries=audit_entries,
        role=session.get("role"),
        active_mode=session.get("active_mode", "supervisor"),
    )




# -----------------------------------------------
# FINANCE OFFICER DASHBOARD: BUDGETS AND EXPENSES
# -----------------------------------------------
@app.route("/finance-officer")
@role_required("finance_officer")
def finance_officer_dashboard():
    """Show budgets and expenses using the actual activity_name schema."""
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    try:
        budgets = connection.execute("""
            SELECT
                b.id,
                b.activity_name,
                b.activity_name AS name,
                b.planned_amount,
                b.start_date,
                b.end_date,
                COALESCE(SUM(e.amount), 0) AS total_expenses,
                COALESCE(SUM(CASE WHEN e.payment_status = 'Paid'
                    THEN e.amount ELSE 0 END), 0) AS paid_expenses,
                COALESCE(SUM(CASE WHEN e.payment_status = 'Unpaid'
                    THEN e.amount ELSE 0 END), 0) AS unpaid_expenses
            FROM budgets b
            LEFT JOIN expenses e ON e.budget_id = b.id
            GROUP BY b.id, b.activity_name, b.planned_amount,
                     b.start_date, b.end_date
            ORDER BY b.id DESC
        """).fetchall()

        expense_rows = connection.execute("""
            SELECT e.id, e.budget_id, e.description, e.amount,
                   e.expense_date, e.payment_status,
                   b.activity_name AS budget_name
            FROM expenses e
            JOIN budgets b ON b.id = e.budget_id
            ORDER BY e.expense_date DESC, e.id DESC
        """).fetchall()

        budget_options = connection.execute("""
            SELECT id, activity_name, activity_name AS name
            FROM budgets
            ORDER BY activity_name COLLATE NOCASE
        """).fetchall()

        totals = connection.execute("""
            SELECT
                COALESCE((SELECT SUM(planned_amount) FROM budgets), 0) AS total_budget,
                COALESCE((SELECT SUM(amount) FROM expenses
                          WHERE payment_status = 'Paid'), 0) AS paid_expenses,
                COALESCE((SELECT SUM(amount) FROM expenses
                          WHERE payment_status = 'Unpaid'), 0) AS unpaid_expenses,
                COALESCE((SELECT SUM(amount) FROM expenses), 0) AS total_expenses
        """).fetchone()
    finally:
        connection.close()

    total_budget = float(totals["total_budget"])
    paid_expenses = float(totals["paid_expenses"])
    unpaid_expenses = float(totals["unpaid_expenses"])
    total_expenses = float(totals["total_expenses"])
    remaining = total_budget - total_expenses

    return render_template(
        "finance_officer_dashboard.html",
        budgets=budgets,
        expenses_list=expense_rows,
        budget_options=budget_options,
        total_budget=f"{total_budget:,.2f}",
        paid_expenses=f"{paid_expenses:,.2f}",
        unpaid_expenses=f"{unpaid_expenses:,.2f}",
        total_expenses=f"{total_expenses:,.2f}",
        remaining=f"{remaining:,.2f}",
        chart_spent=max(total_expenses, 0),
        chart_remaining=max(remaining, 0),
        chart_unpaid=max(unpaid_expenses, 0),
        role=session.get("role"),
        active_mode=session.get("active_mode", "standard"),
    )

@app.route("/finance/budgets/new", methods=["POST"])
@role_required("finance_officer")
def add_budget():
    activity_name = request.form.get(
        "activity_name", request.form.get("name", "")
    ).strip()
    amount = valid_positive_amount(request.form.get("planned_amount", ""))
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()

    if not activity_name or len(activity_name) > 120:
        flash("Activity name is required and must be 120 characters or fewer.", "error")
        return redirect(url_for("finance_officer_dashboard"))
    if amount is None:
        flash("Enter a valid positive budget amount with up to two decimal places.", "error")
        return redirect(url_for("finance_officer_dashboard"))

    try:
        parsed_start = date.fromisoformat(start_date)
        parsed_end = date.fromisoformat(end_date)
        if parsed_end < parsed_start:
            raise ValueError("End date cannot be earlier than start date.")
    except (ValueError, TypeError):
        flash("Enter valid start and end dates. The end date cannot be before the start date.", "error")
        return redirect(url_for("finance_officer_dashboard"))

    connection = sqlite3.connect(DATABASE_NAME)
    try:
        connection.execute("""
            INSERT INTO budgets (activity_name, planned_amount, start_date, end_date)
            VALUES (?, ?, ?, ?)
        """, (activity_name, float(amount), parsed_start.isoformat(), parsed_end.isoformat()))
        connection.commit()
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Budget creation failed.")
        flash("Could not save the budget. Please check the database structure.", "error")
    else:
        flash("Budget added successfully.", "success")
    finally:
        connection.close()
    return redirect(url_for("finance_officer_dashboard"))

@app.route("/finance/expenses/new", methods=["POST"])
@role_required("finance_officer")
def add_finance_expense():
    budget_id = request.form.get("budget_id", type=int)
    description = request.form.get("description", "").strip()
    amount = valid_positive_amount(request.form.get("amount", ""))
    expense_date = request.form.get("expense_date", "").strip()
    payment_status = request.form.get("payment_status", "Unpaid").strip()

    if not budget_id:
        flash("Choose a budget for this expense.", "error")
        return redirect(url_for("finance_officer_dashboard"))
    if not description or len(description) > 200:
        flash("Expense description is required and must be 200 characters or fewer.", "error")
        return redirect(url_for("finance_officer_dashboard"))
    if amount is None:
        flash("Enter a valid positive expense amount with up to two decimal places.", "error")
        return redirect(url_for("finance_officer_dashboard"))
    try:
        parsed_date = date.fromisoformat(expense_date)
    except (ValueError, TypeError):
        flash("Enter a valid expense date.", "error")
        return redirect(url_for("finance_officer_dashboard"))
    if payment_status not in {"Paid", "Unpaid"}:
        flash("Payment status must be Paid or Unpaid.", "error")
        return redirect(url_for("finance_officer_dashboard"))

    connection = sqlite3.connect(DATABASE_NAME)
    try:
        exists = connection.execute("SELECT 1 FROM budgets WHERE id = ?", (budget_id,)).fetchone()
        if not exists:
            flash("The selected budget could not be found.", "error")
            return redirect(url_for("finance_officer_dashboard"))
        connection.execute("""
            INSERT INTO expenses (budget_id, description, amount, expense_date, payment_status)
            VALUES (?, ?, ?, ?, ?)
        """, (budget_id, description, float(amount), parsed_date.isoformat(), payment_status))
        connection.commit()
    finally:
        connection.close()
    flash("Expense added successfully.", "success")
    return redirect(url_for("finance_officer_dashboard"))


@app.route("/finance/budgets/<int:budget_id>/edit", methods=["GET", "POST"])
@role_required("finance_officer")
def edit_budget(budget_id):
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    try:
        budget = connection.execute("""
            SELECT *, activity_name AS name
            FROM budgets WHERE id = ?
        """, (budget_id,)).fetchone()
        if budget is None:
            abort(404)

        if request.method == "POST":
            activity_name = request.form.get(
                "activity_name", request.form.get("name", "")
            ).strip()
            amount = valid_positive_amount(request.form.get("planned_amount", ""))
            start_date = request.form.get("start_date", "").strip()
            end_date = request.form.get("end_date", "").strip()

            try:
                parsed_start = date.fromisoformat(start_date)
                parsed_end = date.fromisoformat(end_date)
                if parsed_end < parsed_start:
                    raise ValueError("End date cannot be earlier than start date.")
            except (ValueError, TypeError):
                parsed_start = None
                parsed_end = None

            if (not activity_name or len(activity_name) > 120 or amount is None
                    or parsed_start is None or parsed_end is None):
                flash("Check the activity name, amount, start date, and end date.", "error")
                return render_template("finance_edit.html", item=budget, item_type="budget")

            connection.execute("""
                UPDATE budgets
                SET activity_name = ?, planned_amount = ?, start_date = ?, end_date = ?
                WHERE id = ?
            """, (activity_name, float(amount), parsed_start.isoformat(),
                  parsed_end.isoformat(), budget_id))
            connection.commit()
            flash("Budget updated successfully.", "success")
            return redirect(url_for("finance_officer_dashboard"))

        return render_template("finance_edit.html", item=budget, item_type="budget")
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Budget update failed.")
        flash("Could not update the budget.", "error")
        return redirect(url_for("finance_officer_dashboard"))
    finally:
        connection.close()

@app.route("/finance/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@role_required("finance_officer")
def edit_finance_expense(expense_id):
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    try:
        expense = connection.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        if expense is None:
            abort(404)

        budget_options = connection.execute("""
            SELECT id, activity_name, activity_name AS name
            FROM budgets
            ORDER BY activity_name COLLATE NOCASE
        """).fetchall()

        if request.method == "POST":
            budget_id = request.form.get("budget_id", type=int)
            description = request.form.get("description", "").strip()
            amount = valid_positive_amount(request.form.get("amount", ""))
            expense_date = request.form.get("expense_date", "").strip()
            payment_status = request.form.get("payment_status", "Unpaid").strip()

            try:
                parsed_date = date.fromisoformat(expense_date)
            except (ValueError, TypeError):
                parsed_date = None

            valid_budget = connection.execute(
                "SELECT 1 FROM budgets WHERE id = ?", (budget_id,)
            ).fetchone() if budget_id else None

            if (not valid_budget or not description or len(description) > 200
                    or amount is None or parsed_date is None
                    or payment_status not in {"Paid", "Unpaid"}):
                flash("Check the budget, description, amount, date, and payment status.", "error")
                return render_template(
                    "finance_edit.html", item=expense,
                    item_type="expense", budget_options=budget_options
                )

            connection.execute("""
                UPDATE expenses
                SET budget_id = ?, description = ?, amount = ?,
                    expense_date = ?, payment_status = ?
                WHERE id = ?
            """, (budget_id, description, float(amount),
                  parsed_date.isoformat(), payment_status, expense_id))
            connection.commit()
            flash("Expense updated successfully.", "success")
            return redirect(url_for("finance_officer_dashboard"))

        return render_template(
            "finance_edit.html", item=expense,
            item_type="expense", budget_options=budget_options
        )
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Expense update failed.")
        flash("Could not update the expense.", "error")
        return redirect(url_for("finance_officer_dashboard"))
    finally:
        connection.close()

# -----------------------------------------------
# RUN ORGFINANCE APPLICATION
# -----------------------------------------------
if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )