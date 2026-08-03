import sqlite3
from datetime import datetime
from models.user import User
from werkzeug.security import check_password_hash


class BankManager:

    def __init__(self, db_name="bank.db"):
        self.db_name = db_name


    def connect(self):

        db = sqlite3.connect(
            self.db_name,
            timeout=10
        )

        db.row_factory = sqlite3.Row

        db.execute(
            "PRAGMA foreign_keys = ON"
        )

        return db



    # Update Customer
    def update_customer(self, customer_id, full_name, national_id, phone, email):

        db = self.connect()

        try:

            cursor = db.cursor()

            cursor.execute("""
            UPDATE Customers
            SET full_name = ?,
                national_id = ?,
                phone = ?,
                email = ?
            WHERE customer_id = ?
            """,
            (
                full_name,
                national_id,
                phone,
                email,
                customer_id
            ))

            db.commit()

            return True

        except sqlite3.Error:

            db.rollback()
            return False

        finally:
            db.close()


    # Delete Customer
    def delete_customer(self, customer_id):

        db = self.connect()

        try:

            cursor = db.cursor()

            cursor.execute("""
                DELETE FROM Customers
                WHERE customer_id = ?
            """, (customer_id,))

            db.commit()

            # لو ما انحذف أي صف (customer_id مش موجود أصلاً)
            return cursor.rowcount > 0

        except sqlite3.IntegrityError:

            # في حسابات (Accounts) مرتبطة بهاد العميل بعد
            db.rollback()
            return False

        finally:

            db.close()


    # Find Customer By National ID
    def find_customer_by_id(self, national_id):

        db = self.connect()

        try:

            cursor = db.cursor()

            cursor.execute("""
                SELECT *
                FROM Customers
                WHERE national_id = ?
            """, (national_id,))

            return cursor.fetchone()

        finally:

            db.close()



    # Get Account (للتحقق من ملكية الحساب)
    def get_account(self, account_id):

        db = self.connect()

        try:

            cursor = db.cursor()

            cursor.execute("""
                SELECT *
                FROM Accounts
                WHERE account_id = ?
            """, (account_id,))

            return cursor.fetchone()

        finally:

            db.close()



    # Add Customer
    def add_customer(self, customer):

        db = self.connect()

        try:

            cursor = db.cursor()

            cursor.execute("""
            INSERT INTO Customers
            (
                full_name,
                national_id,
                phone,
                email
            )

            VALUES (?, ?, ?, ?)

            """,
            (
                customer.full_name,
                customer.national_id,
                customer.phone,
                customer.email
            ))


            db.commit()

            return True


        except sqlite3.IntegrityError:

            db.rollback()
            return False


        finally:

            db.close()



    # Create Account
    def create_account(self, customer_id, account_number, account_type):

        db = self.connect()

        try:

            cursor = db.cursor()

            cursor.execute("""
            INSERT INTO Accounts
            (
                customer_id,
                account_number,
                account_type
            )

            VALUES (?, ?, ?)

            """,
            (
                customer_id,
                account_number,
                account_type
            ))


            db.commit()

            return True


        except sqlite3.IntegrityError:

            db.rollback()
            return False


        finally:

            db.close()



    # Deposit
    def deposit(self, account_id, amount):

        db = self.connect()

        try:

            cursor = db.cursor()


            cursor.execute("""
            UPDATE Accounts
            SET balance = balance + ?
            WHERE account_id = ?
            """,
            (
                amount,
                account_id
            ))


            if cursor.rowcount == 0:
                db.rollback()
                return False



            cursor.execute("""
            INSERT INTO Transactions
            (
                account_id,
                transaction_type,
                amount,
                description,
                transaction_date
            )

            VALUES (?, ?, ?, ?, ?)

            """,
            (
                account_id,
                "Deposit",
                amount,
                "Cash Deposit",
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))


            db.commit()

            return True


        except sqlite3.Error:

            db.rollback()
            return False


        finally:

            db.close()
    
        # Withdraw
    def withdraw(self, account_id, amount):

        db = self.connect()

        try:

            cursor = db.cursor()


            cursor.execute("""
            SELECT balance
            FROM Accounts
            WHERE account_id = ?
            """,
            (account_id,))


            balance = cursor.fetchone()


            if balance is None:
                return False


            if balance["balance"] < amount:
                return False



            cursor.execute("""
            UPDATE Accounts
            SET balance = balance - ?
            WHERE account_id = ?
            """,
            (
                amount,
                account_id
            ))



            cursor.execute("""
            INSERT INTO Transactions
            (
                account_id,
                transaction_type,
                amount,
                description,
                transaction_date
            )

            VALUES (?, ?, ?, ?, ?)

            """,
            (
                account_id,
                "Withdraw",
                amount,
                "Cash Withdraw",
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))


            db.commit()

            return True


        except sqlite3.Error:

            db.rollback()
            return False


        finally:

            db.close()



    # Transfer
    def transfer(self, sender_id, receiver_id, amount):

        db = self.connect()

        try:

            cursor = db.cursor()


            # منع التحويل لنفس الحساب
            if str(sender_id) == str(receiver_id):
                return False


            # فحص حساب المرسل
            cursor.execute("""
            SELECT balance
            FROM Accounts
            WHERE account_id = ?
            """,
            (sender_id,))


            sender = cursor.fetchone()


            if sender is None:
                return False


            if sender["balance"] < amount:
                return False



            # فحص حساب المستقبل
            cursor.execute("""
            SELECT account_id
            FROM Accounts
            WHERE account_id = ?
            """,
            (receiver_id,))


            receiver = cursor.fetchone()


            if receiver is None:
                return False



            # خصم من المرسل
            cursor.execute("""
            UPDATE Accounts
            SET balance = balance - ?
            WHERE account_id = ?
            """,
            (
                amount,
                sender_id
            ))



            # إضافة للمستقبل
            cursor.execute("""
            UPDATE Accounts
            SET balance = balance + ?
            WHERE account_id = ?
            """,
            (
                amount,
                receiver_id
            ))



            # Transaction للمرسل
            cursor.execute("""
            INSERT INTO Transactions
            (
                account_id,
                transaction_type,
                amount,
                description,
                transaction_date
            )

            VALUES (?, ?, ?, ?, ?)

            """,
            (
                sender_id,
                "Transfer Out",
                amount,
                f"Transfer to account {receiver_id}",
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))



            # Transaction للمستقبل
            cursor.execute("""
            INSERT INTO Transactions
            (
                account_id,
                transaction_type,
                amount,
                description,
                transaction_date
            )

            VALUES (?, ?, ?, ?, ?)

            """,
            (
                receiver_id,
                "Transfer In",
                amount,
                f"Transfer from account {sender_id}",
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))



            db.commit()

            return True


        except sqlite3.Error:

            db.rollback()
            return False


        finally:

            db.close()




    # Get Transactions
    def get_transactions(self, account_id):

        db = self.connect()

        try:

            cursor = db.cursor()


            cursor.execute("""
            SELECT
                transaction_type,
                amount,
                description,
                transaction_date

            FROM Transactions

            WHERE account_id = ?

            ORDER BY transaction_id DESC

            """,
            (account_id,))


            return cursor.fetchall()


        finally:

            db.close()




    # Add User
    def add_user(self, user):

        db = self.connect()

        try:

            cursor = db.cursor()


            cursor.execute("""
            INSERT INTO Users
            (
                username,
                password,
                role,
                customer_id
            )

            VALUES (?, ?, ?, ?)

            """,
            (
                user.username,
                user.password,
                user.role,
                user.customer_id
            ))


            db.commit()

            return True



        except sqlite3.IntegrityError:

            db.rollback()
            raise



        finally:

            db.close()



    # Get User
    def get_user(self, username):

        db = self.connect()

        try:

            cursor = db.cursor()


            cursor.execute("""
            SELECT *
            FROM Users
            WHERE username = ?

            """,
            (username,))


            return cursor.fetchone()



        finally:

            db.close()