
import sqlite3

connection = sqlite3.connect("orgfinance.db")

try:
    columns = connection.execute(
        "PRAGMA table_info(transactions)"
    ).fetchall()

    column_names = [column[1] for column in columns]

    if "budget_id" not in column_names:
        connection.execute("""
            ALTER TABLE transactions
            ADD COLUMN budget_id INTEGER
            REFERENCES budgets(id)
        """)

        connection.commit()
        print("budget_id column added successfully!")
    else:
        print("budget_id column already exists.")

finally:
    connection.close()