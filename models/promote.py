import sqlite3

db = sqlite3.connect("bank.db")
db.execute("UPDATE Users SET role = 'Admin' WHERE username = 'amro'")
db.commit()
db.close()
print("تم")