
import os
import sqlite3


# Always use the database file located beside this Python file.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(BASE_DIR, "orgfinance.db")


def get_connection():
    """Create a connection to the OrgFinance SQLite database."""
    return sqlite3.connect(DATABASE_NAME)


def create_database():
    connection = get_connection()

    try:
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
        print("Database and transactions table are ready!")

    finally:
        connection.close()


def add_transaction(transaction_type, amount, description, category, date):
    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO transactions
            (transaction_type, amount, description, category, transaction_date)
            VALUES (?, ?, ?, ?, ?)
        """, (transaction_type, amount, description, category, date))

        connection.commit()
        print("Transaction saved successfully!")

    finally:
        connection.close()


def show_transactions():
    connection = get_connection()

    try:
        records = connection.execute("""
            SELECT id, transaction_type, amount, description,
                   category, transaction_date
            FROM transactions
            ORDER BY id
        """).fetchall()

        for record in records:
            print(record)

    finally:
        connection.close()


if __name__ == "__main__":
    create_database()
    show_transactions()
