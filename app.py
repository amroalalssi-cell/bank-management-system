import os
import re
import sqlite3
from functools import wraps

from flask import Flask, render_template, request, redirect, flash, session
from database import Database
from models.user import User
from models.customer import Customer
from bank_manager import BankManager
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# secret_key لازم ياخد من environment variable بالإنتاج
# مثال: export SECRET_KEY="قيمة عشوائية طويلة"
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())

bank = BankManager()
database = Database()
database.create_tables()
database.close()


# ---------------------------------------------------------------
# Decorators للتحقق من تسجيل الدخول والصلاحيات
# ---------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            flash("يرجى تسجيل الدخول أولاً", "danger")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            flash("يرجى تسجيل الدخول أولاً", "danger")
            return redirect("/login")
        if session.get("role") != "Admin":
            flash("غير مصرح لك بالوصول لهذه الصفحة", "danger")
            return redirect("/dashboard")
        return f(*args, **kwargs)
    return decorated


def get_account_owner(account_id):
    """يرجع customer_id تبع صاحب الحساب، أو None لو الحساب مش موجود."""
    db = sqlite3.connect("bank.db")
    cursor = db.cursor()
    cursor.execute(
        "SELECT customer_id FROM Accounts WHERE account_id = ?",
        (account_id,)
    )
    row = cursor.fetchone()
    db.close()
    return row[0] if row else None


def owns_account_or_admin(account_id):
    """True لو الأدمن، أو لو الحساب فعلاً ملك المستخدم الحالي."""
    if session.get("role") == "Admin":
        return True
    owner_id = get_account_owner(account_id)
    return owner_id is not None and str(owner_id) == str(session.get("customer_id"))


# ---------------------------------------------------------------
# صفحات عامة
# ---------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/dashboard")
@login_required
def dashboard():
    db = sqlite3.connect("bank.db")
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) FROM Customers")
    total_customers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM Accounts")
    total_accounts = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(balance) FROM Accounts")
    total_balance = cursor.fetchone()[0]

    if total_balance is None:
        total_balance = 0

    db.close()

    return render_template(
        "dashboard.html",
        total_customers=total_customers,
        total_accounts=total_accounts,
        total_balance=total_balance
    )


# ---------------------------------------------------------------
# إدارة العملاء (Admin فقط)
# ---------------------------------------------------------------

@app.route("/customers")
@admin_required
def customers():
    db = bank.connect()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM Customers")
    customers = cursor.fetchall()

    db.close()

    return render_template("customers.html", customers=customers)


@app.route("/add_customer", methods=["GET", "POST"])
@admin_required
def add_customer():

    if request.method == "POST":

        full_name = request.form["full_name"].strip()
        national_id = request.form["national_id"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip()

        if not full_name or not national_id or not phone or not email:
            flash("Please fill all fields", "danger")
            return render_template("add_customer.html")

        if len(full_name) < 3:
            flash("Name must be at least 3 characters", "danger")
            return render_template("add_customer.html")

        if not national_id.isdigit() or len(national_id) != 9:
            flash("National ID must contain 9 numbers", "danger")
            return render_template("add_customer.html")

        if bank.find_customer_by_id(national_id):
            flash("Customer already exists", "danger")
            return render_template("add_customer.html")

        if not phone.isdigit() or len(phone) < 9:
            flash("Invalid phone number", "danger")
            return render_template("add_customer.html")

        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_pattern, email):
            flash("Invalid email address", "danger")
            return render_template("add_customer.html")

        customer = Customer(full_name, national_id, phone, email)

        added = bank.add_customer(customer)

        if not added:
            flash("Customer already exists", "danger")
            return render_template("add_customer.html")

        flash("Customer added successfully", "success")
        return redirect("/customers")

    return render_template("add_customer.html")


@app.route("/edit_customer/<int:customer_id>", methods=["GET", "POST"])
@admin_required
def edit_customer(customer_id):

    if request.method == "POST":

        bank.update_customer(
            customer_id,
            request.form["full_name"],
            request.form["national_id"],
            request.form["phone"],
            request.form["email"]
        )

        return redirect("/customers")

    db = bank.connect()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM Customers WHERE customer_id = ?",
        (customer_id,)
    )

    customer = cursor.fetchone()

    db.close()

    return render_template("edit_customer.html", customer=customer)


@app.route("/delete_customer/<int:customer_id>", methods=["POST"])
@admin_required
def delete_customer(customer_id):

    deleted = bank.delete_customer(customer_id)

    if not deleted:
        flash("لا يمكن حذف عميل لديه حسابات مرتبطة", "danger")
    else:
        flash("تم حذف العميل بنجاح", "success")

    return redirect("/customers")


@app.route("/view_customer/<int:customer_id>")
@admin_required
def view_customer(customer_id):

    db = bank.connect()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM Customers WHERE customer_id = ?",
        (customer_id,)
    )

    customer = cursor.fetchone()

    db.close()

    return render_template("view_customer.html", customer=customer)


# ---------------------------------------------------------------
# الحسابات البنكية
# ---------------------------------------------------------------

@app.route("/accounts")
@login_required
def accounts():

    db = bank.connect()
    cursor = db.cursor()

    cursor.execute("""
    SELECT
        Accounts.account_id,
        Customers.full_name,
        Accounts.account_number,
        Accounts.account_type,
        Accounts.balance,
        Accounts.customer_id

    FROM Accounts
    JOIN Customers ON Accounts.customer_id = Customers.customer_id
    """)

    accounts = cursor.fetchall()

    db.close()

    is_admin = session.get("role") == "Admin"

    return render_template(
        "accounts.html",
        accounts=accounts,
        is_admin=is_admin,
        my_customer_id=session.get("customer_id")
    )


@app.route("/create_account/<int:customer_id>", methods=["GET", "POST"])
@admin_required
def create_account(customer_id):

    if request.method == "POST":

        created = bank.create_account(
            customer_id,
            request.form["account_number"],
            request.form["account_type"]
        )

        if not created:
            flash("رقم الحساب مستخدم مسبقاً", "danger")
            return render_template("create_account.html", customer_id=customer_id)

        flash("تم إنشاء الحساب بنجاح", "success")
        return redirect("/accounts")

    return render_template("create_account.html", customer_id=customer_id)


@app.route("/view_account/<int:account_id>")
@login_required
def view_account(account_id):

    if not owns_account_or_admin(account_id):
        flash("غير مصرح لك بعرض هذا الحساب", "danger")
        return redirect("/accounts")

    db = bank.connect()
    cursor = db.cursor()

    cursor.execute("""
    SELECT
        Accounts.account_id,
        Customers.full_name,
        Accounts.account_number,
        Accounts.account_type,
        Accounts.balance

    FROM Accounts
    JOIN Customers ON Accounts.customer_id = Customers.customer_id
    WHERE Accounts.account_id = ?
    """, (account_id,))

    account = cursor.fetchone()

    db.close()

    return render_template("view_account.html", account=account)


@app.route("/transactions/<int:account_id>")
@login_required
def transactions(account_id):

    if not owns_account_or_admin(account_id):
        flash("غير مصرح لك بعرض هذا السجل", "danger")
        return redirect("/accounts")

    transactions = bank.get_transactions(account_id)

    return render_template("transactions.html", transactions=transactions)


# ---------------------------------------------------------------
# عمليات مالية
# ---------------------------------------------------------------

def parse_amount(amount_input):
    """يرجع (amount, error_message). error_message = None لو تمام."""
    try:
        amount = float(amount_input.strip())
    except (ValueError, AttributeError):
        return None, "Invalid amount format"

    if amount <= 0:
        return None, "Amount must be greater than zero"

    return amount, None


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():

    if request.method == "POST":

        account_id = request.form["account_id"]

        amount, error = parse_amount(request.form["amount"])
        if error:
            flash(error, "danger")
            return render_template("deposit.html")

        if not owns_account_or_admin(account_id):
            flash("غير مصرح لك بالتعامل مع هذا الحساب", "danger")
            return render_template("deposit.html")

        success = bank.deposit(account_id, amount)

        if not success:
            flash("رقم الحساب غير موجود", "danger")
            return render_template("deposit.html")

        flash("تم الإيداع بنجاح", "success")
        return redirect("/accounts")

    return render_template("deposit.html")


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():

    if request.method == "POST":

        account_id = request.form["account_id"]

        amount, error = parse_amount(request.form["amount"])
        if error:
            flash(error, "danger")
            return render_template("withdraw.html")

        if not owns_account_or_admin(account_id):
            flash("غير مصرح لك بالتعامل مع هذا الحساب", "danger")
            return render_template("withdraw.html")

        success = bank.withdraw(account_id, amount)

        if not success:
            flash("الرصيد غير كافٍ أو الحساب غير موجود", "danger")
            return render_template("withdraw.html")

        flash("تم السحب بنجاح", "success")
        return redirect("/accounts")

    return render_template("withdraw.html")


@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():

    if request.method == "POST":

        sender_id = request.form["sender_id"]
        receiver_id = request.form["receiver_id"]

        amount, error = parse_amount(request.form["amount"])
        if error:
            flash(error, "danger")
            return render_template("transfer.html")

        if not owns_account_or_admin(sender_id):
            flash("غير مصرح لك بالتحويل من هذا الحساب", "danger")
            return render_template("transfer.html")

        success = bank.transfer(sender_id, receiver_id, amount)

        if not success:
            flash("فشل التحويل: تأكد من الأرصدة وأرقام الحسابات", "danger")
            return render_template("transfer.html")

        flash("تم التحويل بنجاح", "success")
        return redirect("/accounts")

    return render_template("transfer.html")


# ---------------------------------------------------------------
# المصادقة
# ---------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]

        password = generate_password_hash(
            request.form["password"]
        )

        # الدور دايماً "Customer" بالتسجيل الذاتي.
        # ترقية مستخدم لأدمن تصير يدوياً من قاعدة البيانات فقط.
        role = "Customer"

        customer_id = request.form.get("customer_id", "").strip()

        if customer_id == "":
            customer_id = None
        else:
            # تحقق إن الـ Customer ID فعلاً موجود قبل المحاولة
            db = sqlite3.connect("bank.db")
            cursor = db.cursor()
            cursor.execute(
                "SELECT 1 FROM Customers WHERE customer_id = ?",
                (customer_id,)
            )
            exists = cursor.fetchone()
            db.close()

            if not exists:
                flash("رقم Customer ID غير موجود، اتركه فارغاً أو تأكد من الرقم", "danger")
                return redirect("/register")

        user = User(username, password, role, customer_id)

        try:
            bank.add_user(user)
            flash("تم إنشاء الحساب بنجاح", "success")
            return redirect("/login")

        except sqlite3.IntegrityError:
            flash("اسم المستخدم موجود مسبقاً", "danger")
            return redirect("/register")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = bank.get_user(username)

        if user and check_password_hash(user[2], password):

            session["username"] = user[1]
            session["role"] = user[3]
            session["customer_id"] = user[4]

            return redirect("/dashboard")

        else:
            flash("اسم المستخدم أو كلمة المرور خطأ")
            return redirect("/login")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("تم تسجيل الخروج بنجاح", "success")
    return redirect("/login")


if __name__ == "__main__":
    # لا تشغّل debug=True بالإنتاج. فعّلها فقط محلياً عبر:
    # export FLASK_DEBUG=1
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")