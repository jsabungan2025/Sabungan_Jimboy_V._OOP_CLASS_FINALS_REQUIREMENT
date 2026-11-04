"""Financial dashboard calculations for OrgFinance."""

from transaction_repository import SQLiteTransactionRepository


class FinancialDashboard:
    """Calculates totals using an injected transaction repository."""

    def __init__(self, transaction_repository):
        self.__repository = transaction_repository

    def get_financial_summary(self):
        total_income = 0.0
        total_expenses = 0.0

        for transaction in self.__repository.get_all():
            transaction_type = transaction[1]
            amount = float(transaction[2])
            if transaction_type == "Income":
                total_income += amount
            elif transaction_type == "Expense":
                total_expenses += amount

        available_cash = total_income - total_expenses
        return total_income, total_expenses, available_cash


def get_financial_summary(repository=None):
    """Backward-compatible function; accepts the app's configured repository."""
    active_repository = repository or SQLiteTransactionRepository()
    dashboard = FinancialDashboard(active_repository)
    return dashboard.get_financial_summary()


def display_dashboard(repository=None):
    income, expenses, cash = get_financial_summary(repository)
    print("\n===== ORGFINANCE DASHBOARD =====")
    print(f"Total Income:     PHP {income:,.2f}")
    print(f"Total Expenses:   PHP {expenses:,.2f}")
    print(f"Available Cash:   PHP {cash:,.2f}")
    print("================================")


if __name__ == "__main__":
    display_dashboard()
