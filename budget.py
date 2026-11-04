
class Budget:
    def __init__(self, activity_name, planned_amount):
        self.activity_name = activity_name

        if planned_amount >= 0:
            self.__planned_amount = planned_amount
        else:
            raise ValueError("Budget cannot be negative.")

    def get_planned_amount(self):
        return self.__planned_amount

    def set_planned_amount(self, new_amount):
        if new_amount >= 0:
            self.__planned_amount = new_amount
        else:
            print("Error: Budget cannot be negative.")

    def calculate_remaining(self, expenses):
        return self.__planned_amount - expenses


# Create a Budget object
foundation_day = Budget("Foundation Day", 4000)

# Display budget information
print("Activity:", foundation_day.activity_name)
print("Planned Budget: PHP", foundation_day.get_planned_amount())

# Calculate remaining budget
expenses = 2500
remaining = foundation_day.calculate_remaining(expenses)

print("Expenses: PHP", expenses)
print("Remaining Budget: PHP", remaining)

# Test changing the budget
foundation_day.set_planned_amount(5000)
print("Updated Budget: PHP", foundation_day.get_planned_amount())