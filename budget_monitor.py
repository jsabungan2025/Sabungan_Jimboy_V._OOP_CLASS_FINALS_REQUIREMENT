
import sqlite3


def get_budget_report(budget_id, database_name="orgfinance.db"):
    connection = sqlite3.connect(database_name)

    try:
        budget = connection.execute("""
            SELECT activity_name, planned_amount
            FROM budgets
            WHERE id = ?
        """, (budget_id,)).fetchone()

        if budget is None:
            return None

        activity_name, planned_amount = budget

        actual_expenses = connection.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE transaction_type = 'Expense'
              AND budget_id = ?
        """, (budget_id,)).fetchone()[0]

        remaining_budget = planned_amount - actual_expenses

        return {
            "activity_name": activity_name,
            "planned_amount": planned_amount,
            "actual_expenses": actual_expenses,
            "remaining_budget": remaining_budget
        }
    finally:
        connection.close()


if __name__ == "__main__":
    report = get_budget_report(1)

    if report is None:
        print("Budget not found. Check the budget ID.")
    else:
        print("\n===== BUDGET MONITOR =====")
        print("Activity:", report["activity_name"])
        print(f"Planned Budget: PHP {report['planned_amount']:,.2f}")
        print(f"Actual Expenses: PHP {report['actual_expenses']:,.2f}")
        print(f"Remaining Budget: PHP {report['remaining_budget']:,.2f}")

        if report["remaining_budget"] < 0:
            print("Status: OVER BUDGET")
        else:
            print("Status: WITHIN BUDGET")