
from transaction import Transaction
from transaction_repository import SQLiteTransactionRepository

repository = SQLiteTransactionRepository()

new_transaction = Transaction(
    "Income",
    1500,
    "Fundraising proceeds",
    "Fundraising",
    "2026-10-09"
)

# Save the transaction object to SQLite
repository.add(new_transaction)

print("Transaction saved successfully!")
print("\nAll transactions in the database:")

for record in repository.get_all():
    print(record)