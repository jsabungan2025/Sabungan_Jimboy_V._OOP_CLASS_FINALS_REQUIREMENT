"""Role-based users for OrgFinance.

Inheritance: each role-specific user inherits from User.
Polymorphism: each subclass provides its own get_permissions() method.
Encapsulation: account data is stored in private attributes and exposed
through read-only properties.
"""


class User:
    """Base class for every authenticated OrgFinance account."""

    ROLE = "user"

    def __init__(self, user_id, username):
        self.__user_id = user_id
        self.__username = str(username)

    @property
    def user_id(self):
        return self.__user_id

    @property
    def username(self):
        return self.__username

    @property
    def role(self):
        return self.ROLE

    def get_permissions(self):
        """Return this user's permissions. Subclasses override this."""
        return frozenset({"view_financial_records"})

    def has_permission(self, permission):
        return permission in self.get_permissions()

    def can_access_role_route(self, allowed_roles):
        return self.role in allowed_roles


class HeadAdmin(User):
    ROLE = "head_admin"

    def get_permissions(self):
        return frozenset({
            "view_financial_records",
            "view_audit_log",
            "manage_users",
            "remove_assistant_admin",
        })


class AssistantAdmin(User):
    ROLE = "assistant_admin"

    def get_permissions(self):
        return frozenset({
            "view_financial_records",
            "view_audit_log",
            "manage_users",
        })


class Supervisor(User):
    ROLE = "supervisor"

    def get_permissions(self):
        return frozenset({
            "view_financial_records",
            "view_audit_log",
            "delete_transaction",
        })


class FinanceOfficer(User):
    ROLE = "finance_officer"

    def get_permissions(self):
        return frozenset({
            "view_financial_records",
            "create_transaction",
            "edit_transaction",
            "manage_budgets",
            "manage_finance_expenses",
        })


class Member(User):
    ROLE = "member"

    def get_permissions(self):
        return frozenset({"view_financial_records"})


_ROLE_CLASSES = {
    "head_admin": HeadAdmin,
    "assistant_admin": AssistantAdmin,
    "supervisor": Supervisor,
    "finance_officer": FinanceOfficer,
    "member": Member,
}


def create_user(role, user_id=None, username=""):
    """Create the correct User subclass for a database/session role."""
    user_class = _ROLE_CLASSES.get(role)
    if user_class is None:
        raise ValueError(f"Unknown OrgFinance role: {role}")
    return user_class(user_id, username)
