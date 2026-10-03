# 🎓 QuizMaster - Modular Quiz & Class Management System

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask Framework](https://img.shields.io/badge/framework-Flask-green.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 100% Passing](https://img.shields.io/badge/tests-100%25%20passing-brightgreen.svg)](tests/)

**QuizMaster** is a full-featured, role-based educational web application designed for managing online classes, creating and taking quizzes, tracking student performance, and generating administrative analytics.

The application has been engineered into a clean, scalable **Modular Blueprint Architecture** using Flask, supporting both **SQLite** (for quick local development and testing) and **PostgreSQL** (for production environments).

---

## ✨ Key Features & User Roles

### 👨‍🎓 Student Role
* **Domain Validation**: Accounts require an authorized email domain (`@student.annauniv.edu`).
* **Class Enrollment**: Request enrollment into teacher-managed classes.
* **Quiz Attempting**: Take published quizzes with immediate score calculation.
* **Response Breakdown**: Review detailed question-by-question responses and correct answers.
* **Performance & Leaderboards**: View class rankings and track historical progress.
* **Feedback System**: Submit feedback and comments to teachers after quiz completion.

### 👩‍🏫 Teacher Role
* **Verification Workflow**: Registration requires a teacher verification code (`1`) and domain validation (`@faculty.annauniv.edu`), subject to Administrator approval.
* **Class Management**: Create and manage subject classes (e.g. `CS101 - Data Structures`).
* **Quiz Builder**: Build multi-question quizzes with customizable difficulty, attempt limits, and availability schedules.
* **Draft & Publish**: Keep quizzes as drafts until ready for publication.
* **Enrollment Moderation**: Review, approve, or reject student enrollment requests.

### 🛡️ Administrator Role
* **Teacher Moderation**: Review pending teacher registrations, approve eligible faculty, or deactivate accounts.
* **System Metrics Dashboard**: Real-time overview of active users, total quizzes created, attempts made, and class stats.
* **Excel Reports Export**: Download comprehensive system data in formatted `.xlsx` spreadsheets for reporting.

---

## 📁 Repository Structure

```text
QuizMaster/
│── app.py                # Main Application Factory (create_app & route alias registration)
│── config.py             # Environment configuration & default application settings
│── database.py           # DB connection manager & SQLite/PostgreSQL syntax normalization
│── init_db.py            # Database schema setup & default admin account seeder
│── schema.sql            # Core database schema tables
│── requirements.txt      # Python dependencies
│── .env.example          # Environment variables template
│── .gitignore            # Git ignore rules for secrets, DB files, and caches
│
├── routes/               # Flask Blueprints (Modular Controllers)
│   ├── auth.py           # Registration, Login, and Logout handlers
│   ├── student.py        # Student dashboard, quiz attempts, and feedback handlers
│   ├── teacher.py        # Teacher dashboard, quiz creation, and student approval handlers
│   ├── admin.py          # Admin dashboard, teacher approvals, and Excel export handlers
│   └── main.py           # Home index and Leaderboard handlers
│
├── templates/            # Jinja2 HTML Templates
├── static/               # CSS Styling, JavaScript, and Images
├── utils/                # Utility Decorators (@login_required, @role_required)
└── tests/                # Automated Pytest Integration Test Suite
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+** installed on your system.

### 2. Clone Repository & Setup Dependencies
```powershell
# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup (`.env`)
Create a `.env` file in the root directory (you can copy `.env.example`):
```powershell
Copy-Item .env.example .env
```

Default configuration (`.env`):
```env
SECRET_KEY=quizmaster_super_secret_key_2026
DB_ENGINE=sqlite
SQLITE_PATH=quizmaster.db

# Admin Seed Credentials
ADMIN_EMAIL=admin@annauniv.edu
ADMIN_PASSWORD=admin123
```

> 💡 **PostgreSQL Setup**: To switch to PostgreSQL, update `.env`:
> ```env
> DB_ENGINE=postgres
> DB_HOST=localhost
> DB_PORT=5432
> DB_NAME=quizmaster
> DB_USER=postgres
> DB_PASSWORD=your_password
> ```

---

### 4. Initialize Database
Initialize tables and seed the default administrator account:
```powershell
py init_db.py
```

### 5. Run the Server
Launch the Flask development server:
```powershell
py app.py
```
Access the application at 👉 **`http://127.0.0.1:5000`**

---

## 🔑 Pre-Configured Credentials

| Role | Email | Password | Details |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@annauniv.edu` | `admin123` | Pre-seeded on DB initialization |
| **Student** | `student1@student.annauniv.edu` | *(Registered by user)* | Must end with `@student.annauniv.edu` |
| **Teacher** | `teacher1@faculty.annauniv.edu` | *(Registered by user)* | Domain: `@faculty.annauniv.edu`<br>Registration Code: `1` |

---

## 🧪 Running Automated Tests

The repository includes an end-to-end integration test suite verifying authentication, quiz creation, student attempts, score calculations, leaderboards, and administrative controls.

Run the test suite:
```powershell
py -m pytest tests/ -v
```

All 11 tests execute in an isolated in-memory/SQLite fixture to ensure zero side effects on your development database.

---

## 📜 License
This project is licensed under the MIT License.
