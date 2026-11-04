"""SQLite persistence layer for OrgFinance transactions."""

import sqlite3


class SQLiteTransactionRepository:
    """Abstracts SQLite operations from the Flask routes and domain model."""

    def __init__(self, database_name="orgfinance.db"):
        self.database_name = database_name

    def _connect(self):
        return sqlite3.connect(self.database_name)

    def get_all(self):
        connection = self._connect()
        try:
            return connection.execute("""
                SELECT id, transaction_type, amount,
                       description, category, transaction_date
                FROM transactions
                ORDER BY id ASC
            """).fetchall()
        finally:
            connection.close()

    def add(self, transaction):
        connection = self._connect()
        try:
            cursor = connection.execute("""
                INSERT INTO transactions (
                    transaction_type, amount, description,
                    category, transaction_date
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                transaction.transaction_type,
                transaction.amount,
                transaction.description,
                transaction.category,
                transaction.transaction_date,
            ))
            connection.commit()
            return cursor.lastrowid
        finally:
            connection.close()

    def get_by_id(self, transaction_id):
        connection = self._connect()
        try:
            return connection.execute("""
                SELECT id, transaction_type, amount,
                       description, category, transaction_date
                FROM transactions
                WHERE id = ?
            """, (transaction_id,)).fetchone()
        finally:
            connection.close()

    def update(self, transaction_id, transaction):
        connection = self._connect()
        try:
            cursor = connection.execute("""
                UPDATE transactions
                SET transaction_type = ?, amount = ?, description = ?,
                    category = ?, transaction_date = ?
                WHERE id = ?
            """, (
                transaction.transaction_type,
                transaction.amount,
                transaction.description,
                transaction.category,
                transaction.transaction_date,
                transaction_id,
            ))
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    def delete(self, transaction_id):
        connection = self._connect()
        try:
            cursor = connection.execute(
                "DELETE FROM transactions WHERE id = ?", (transaction_id,)
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()
