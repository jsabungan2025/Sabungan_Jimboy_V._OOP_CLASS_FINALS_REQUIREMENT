"""Transaction domain model for OrgFinance."""

from decimal import Decimal, InvalidOperation
from datetime import date


class Transaction:
    """A validated income or expense record (encapsulated domain object)."""

    VALID_TYPES = ("Income", "Expense")

    def __init__(
        self,
        transaction_type,
        amount,
        description,
        category,
        transaction_date,
        budget_id=None,
    ):
        if transaction_type not in self.VALID_TYPES:
            raise ValueError("Type must be Income or Expense.")

        try:
            decimal_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Amount must be a valid number.")

        if not decimal_amount.is_finite() or decimal_amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        if max(0, -decimal_amount.as_tuple().exponent) > 2:
            raise ValueError("Amount must have no more than two decimal places.")
        if not isinstance(description, str) or not description.strip():
            raise ValueError("Description cannot be empty.")
        if not isinstance(category, str) or not category.strip():
            raise ValueError("Category cannot be empty.")

        try:
            parsed_date = date.fromisoformat(str(transaction_date))
        except (TypeError, ValueError):
            raise ValueError("Transaction date must be a valid YYYY-MM-DD date.")

        self.__transaction_type = transaction_type
        self.__amount = float(decimal_amount)
        self.__description = description.strip()
        self.__category = category.strip()
        self.__transaction_date = parsed_date.isoformat()
        self.__budget_id = budget_id

    @property
    def transaction_type(self):
        return self.__transaction_type

    @property
    def amount(self):
        return self.__amount

    @property
    def description(self):
        return self.__description

    @property
    def category(self):
        return self.__category

    @property
    def transaction_date(self):
        return self.__transaction_date

    @property
    def budget_id(self):
        return self.__budget_id

    def display_transaction(self):
        return (
            f"{self.__transaction_type}: PHP {self.__amount:,.2f} | "
            f"{self.__description} | {self.__category} | "
            f"{self.__transaction_date}"
        )
