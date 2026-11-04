import sqlite3

DATABASE_NAME = (
    r"C:\Users\Jimboy V. Sabungan\OneDrive\Documents"
    r"\Draft for My Website\OOP\OrgFinance - Copy"
    r"\orgfinance.db"
)

connection = sqlite3.connect(DATABASE_NAME)

try:
    print("Inspecting:", DATABASE_NAME)

    tables = connection.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    print("\n=== TABLES ===")
    for name, schema in tables:
        print(f"\n{name}")
        print(schema)

    print("\n=== USER ROLE COUNTS ===")
    table_names = {row[0] for row in tables}

    if "users" in table_names:
        for role, count in connection.execute("""
            SELECT role, COUNT(*)
            FROM users
            GROUP BY role
        """):
            print(f"{role}: {count}")
    else:
        print("No users table in this database.")

except sqlite3.Error as error:
    print("Database inspection error:", error)

finally:
    connection.close()