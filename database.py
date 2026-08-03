import sqlite3


class Database:

    def __init__(self):
        self.db = sqlite3.connect("bank.db")
        self.cursor = self.db.cursor()

        self.cursor.execute(
            "PRAGMA foreign_keys = ON"
        )


    def create_tables(self):

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Customers(
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                national_id TEXT UNIQUE NOT NULL,
                phone TEXT,
                email TEXT
            )
            """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Users(

            user_id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            role TEXT NOT NULL,

            customer_id INTEGER,

            FOREIGN KEY(customer_id)
            REFERENCES Customers(customer_id)

            )
            """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Accounts(
                account_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                account_number TEXT UNIQUE NOT NULL,
                account_type TEXT,
                balance REAL DEFAULT 0,

                FOREIGN KEY(customer_id)
                REFERENCES Customers(customer_id)
            )
            """)


        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS Transactions(

            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,

            account_id INTEGER,

            transaction_type TEXT,

            amount REAL,

            description TEXT,

            transaction_date TEXT,

            FOREIGN KEY(account_id)
            REFERENCES Accounts(account_id)

        )
                """)


        self.db.commit()


    def close(self):
        self.db.close()