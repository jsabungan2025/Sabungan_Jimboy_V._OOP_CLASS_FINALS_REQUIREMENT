
import os
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

# Always use the database in this project's folder.
DATABASE_NAME = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "orgfinance.db"
)

ALLOWED_ROLES = (
    "head_admin",
    "assistant_admin",
    "supervisor",
    "finance_officer",
    "member",
)


def initialize_admin():
    username = input("Create Head Admin username: ").strip()

    if not username or len(username) > 50:
        print("Username must contain 1–50 characters.")
        return

    password = getpass("Create password (minimum 12 characters): ")

    if len(password) < 12:
        print("Password must be at least 12 characters.")
        return

    confirm_password = getpass("Confirm password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    connection = sqlite3.connect(DATABASE_NAME)

    try:
        # Stop instead of accidentally changing an existing user table.
        existing_table = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'users'
        """).fetchone()

        if existing_table:
            print(
                "A users table already exists. "
                "No changes were made."
            )
            return

        connection.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (
                    role IN (
                        'head_admin',
                        'assistant_admin',
                        'supervisor',
                        'finance_officer',
                        'member'
                    )
                ),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        """, (
            username,
            generate_password_hash(password),
            "head_admin"
        ))

        connection.commit()
        print("Initial Head Admin account created successfully.")

    except sqlite3.Error as error:
        connection.rollback()
        print("Database setup failed:", error)

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_admin()
