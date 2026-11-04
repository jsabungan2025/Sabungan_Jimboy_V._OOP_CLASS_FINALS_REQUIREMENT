
import sqlite3


class SQLiteBudgetRepository:
    def __init__(self, database_name="orgfinance.db"):
        self.database_name = database_name

    def create_table(self):
        connection = sqlite3.connect(self.database_name)

        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_name TEXT NOT NULL,
                    planned_amount REAL NOT NULL
                        CHECK (planned_amount >= 0),
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL
                )
            """)

            connection.commit()
        finally:
            connection.close()

    def add(self, budget, start_date, end_date):
        connection = sqlite3.connect(self.database_name)

        try:
            connection.execute("""
                INSERT INTO budgets (
                    activity_name,
                    planned_amount,
                    start_date,
                    end_date
                )
                VALUES (?, ?, ?, ?)
            """, (
                budget.activity_name,
                budget.get_planned_amount(),
                start_date,
                end_date
            ))

            connection.commit()
        finally:
            connection.close()

    def get_all(self):
        connection = sqlite3.connect(self.database_name)

        try:
            return connection.execute("""
                SELECT id, activity_name, planned_amount,
                       start_date, end_date
                FROM budgets
                ORDER BY id
            """).fetchall()
        finally:
            connection.close()