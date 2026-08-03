import sqlite3

db = sqlite3.connect("bank.db")
rows = db.execute("SELECT username, role FROM Users").fetchall()
for row in rows:
    print(row)
db.close()