
from budget import Budget
from budget_repository import SQLiteBudgetRepository

repository = SQLiteBudgetRepository()

# Create the budgets table
repository.create_table()

# Create a budget object
foundation_day = Budget("Foundation Day", 10000)

# Save the budget
repository.add(
    foundation_day,
    "2026-11-15",
    "2026-11-15"
)

print("Budget saved successfully!")
print("\nAll saved budgets:")

for record in repository.get_all():
    print(record)