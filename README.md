# OrgFinance – Organizational Financial Management System

## Project Description

**OrgFinance** is a web-based financial management system developed using Python and Flask. It helps academic organizations manage and monitor their finances by recording income, expenses, budgets, and available cash.

The system provides an organized way to track financial transactions and monitor budget usage.

## Objectives

- Manage organizational budgets.
- Record income and expenses.
- Monitor available funds.
- View transaction history.
- Improve financial tracking and transparency.

## Features

- **Dashboard** – Displays total income, expenses, and available cash.
- **Budget Management** – Create and monitor organizational budgets.
- **Income Management** – Record financial contributions and other income.
- **Expense Management** – Record organizational expenses.
- **Transaction History** – View recorded financial transactions.
- **CRUD Operations** – Create, read, update, and delete authorized records.
- **User Authentication** – Secure login and role-based access.
- **Role-Based Permissions** – Provide different access levels depending on user roles.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| Flask | Web application framework |
| SQLite | Database management |
| HTML | Web page structure |
| CSS | Website styling |
| JavaScript | Interactive elements |
| Jinja2 | HTML templating |
| Visual Studio Code | Development environment |
| Git and GitHub | Version control |

## Object-Oriented Programming Concepts

This project demonstrates the four fundamental OOP principles:

1. **Encapsulation** – Organizes and protects data within classes.
2. **Abstraction** – Hides implementation details through defined interfaces.
3. **Inheritance** – Allows classes to reuse properties and methods from parent classes.
4. **Polymorphism** – Allows different classes to implement shared methods in different ways.

## User Roles

- **Head Admin** – Manages administrative accounts and system oversight.
- **Assistant Admin** – Assists with administrative management.
- **Supervisor** – Monitors financial records and authorized administrative activities.
- **Finance Officer** – Manages budgets, income, and expenses.
- **Member** – Has view-only access to financial information.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/jsabungan2025/Sabungan_Jimboy_V._OOP_CLASS_FINALS_REQUIREMENT.git
```

### 2. Open the Project Folder

```bash
cd Sabungan_Jimboy_V._OOP_CLASS_FINALS_REQUIREMENT
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

### 4. Activate the Virtual Environment

Windows:

```bash
venv\Scripts\activate
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the Application

```bash
python app.py
```

### 7. Open in Your Browser

```text
http://127.0.0.1:5000
```

## Project Structure

```text
OrgFinance/
│
├── app.py
├── database.py
├── transaction.py
├── transaction_repository.py
├── dashboard.py
├── requirements.txt
│
├── templates/
│   ├── dashboard.html
│   ├── history.html
│   └── ...
│
├── static/
│   ├── style.css
│   └── ...
│
└── orgfinance.db
```

*Note: The project structure may change as development continues.*

## Developer

**Name:** Jimboy V. Sabungan  
**Program:** Bachelor of Science in Computer Science  
**Project:** Python Object-Oriented Programming Final Project

## License

This project was developed for academic purposes as part of an Object-Oriented Programming course.
