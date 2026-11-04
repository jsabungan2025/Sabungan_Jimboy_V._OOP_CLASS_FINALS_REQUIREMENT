
import sqlite3


def create_database():
    connection = sqlite3.connect("orgfinance.db")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            transaction_date TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()

    print("Database and transactions table are ready!")


def add_transaction(transaction_type, amount, description, category, date):
    connection = sqlite3.connect("orgfinance.db")

    connection.execute("""
        INSERT INTO transactions
        (transaction_type, amount, description, category, transaction_date)
        VALUES (?, ?, ?, ?, ?)
    """, (transaction_type, amount, description, category, date))

    connection.commit()
    connection.close()

    print("Transaction saved successfully!")


def show_transactions():
    connection = sqlite3.connect("orgfinance.db")

    records = connection.execute("""
        SELECT id, transaction_type, amount, description,
               category, transaction_date
        FROM transactions
        ORDER BY id
    """).fetchall()

    connection.close()

    for record in records:
        print(record)


if __name__ == "__main__":
    create_database()

    add_transaction(
        "Income",
        2000,
        "Membership fees",
        "Membership",
        "2026-10-09"
    )

    add_transaction(
        "Expense",
        800,
        "Event decorations",
        "Supplies",
        "2026-10-09"
    )

    print("\nSaved transactions:")
    show_transactions()