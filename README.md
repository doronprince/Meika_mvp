# Meika (명가) — AI Financial Copilot (Phase 1 MVP)

> **Tagline:** Spend Savvy. Live Fully.  
> **Brand Identity:** Japanese Zen Minimalism ("Zen Garden" Aesthetic: Washi `#FBFBF7`, Sumi `#2F2F2F`, Matcha `#889A7B`).  
> **Target Audience:** International students in Seoul & global campuses navigating financial anxiety.

---

## 🌟 Overview & Key MVP Features

Meika is an **Explainable AI (XAI) Financial Copilot** designed to bridge the "Anxiety-Action Gap" for international students. Instead of imposing restrictive budgeting limits, Meika delivers **automated financial clarity** with four core modules:

1. **🔍 AI Price-Finder & True Economic Cost Engine**:
   - Calculates **Item Price + Public Transit Fare (Bus/Subway)** across Coupang, local supermarkets (Emart Wolgye), and traditional markets (Gyeongdong Market).
   - Generates transparent Buy/Wait recommendations with real-time price trend tracking.

2. **📊 Predictive Budgeting & Run-Rate Risk Analysis**:
   - Analyzes daily spending velocity and forecasts month-end total expenditures against the student monthly budget threshold (₩600,000).
   - Computes a dynamic **Financial Clarity Score (0–100)** and cash-flow risk rating.

3. **🤖 "Wise Guide" XAI Copilot Assistant**:
   - Empathetic conversational assistant providing non-judgmental guidance.
   - Includes explicit **Explainable AI (XAI) Factor Panels** detailing the exact variables and data sources behind every recommendation.

4. **✨ Zen Garden Minimalist UI**:
   - Custom palette designed to reduce cognitive strain (Washi paper background, Sumi ink typography, Matcha green growth accents, and the Ensō Clarity Circle logo).

---

## 🚀 PyCharm Execution Guide

This project is fully configured as a standalone PyCharm Python project.

### Step 1: Open in PyCharm
1. Launch **PyCharm**.
2. Click **Open** and select the project folder:  
   `Meika_MVP` (`/working_dir/c_72e497a5dca52797/Meika_MVP`)

### Step 2: Configure Python Interpreter & Run Configuration
- PyCharm will automatically detect the `.idea` configuration files included in the project.
- A pre-configured run configuration named **`Run Meika Server`** is included in `.idea/runConfigurations/Main.xml`.

### Step 3: Launch Server
- Click the green **Play ▶** button in PyCharm (or run `python main.py` in the terminal).
- Open your web browser to: **`http://127.0.0.1:8000`**

---

## 📁 Directory Structure

```text
Meika_MVP/
├── .idea/                      # PyCharm Project & Run Configurations
│   ├── Meika_MVP.iml
│   ├── modules.xml
│   ├── misc.xml
│   └── runConfigurations/Main.xml
├── app/
│   ├── __init__.py
│   ├── database.py             # SQLite DB setup & Seoul student retail seed data
│   ├── models.py               # Pydantic Schemas & DTOs
│   ├── services/               # Business Logic & XAI Algorithms
│   │   ├── price_finder.py     # True Economic Cost engine
│   │   ├── expense_tracker.py  # Expense analytics & run-rate prediction
│   │   └── xai_copilot.py      # Wise Guide XAI Copilot
│   ├── routers/                # FastAPI Endpoints
│   │   ├── price_router.py
│   │   ├── expense_router.py
│   │   ├── copilot_router.py
│   │   └── dashboard_router.py
│   ├── templates/              # Zen Garden HTML Templates (Jinja2)
│   │   ├── base.html
│   │   ├── index.html          # Dashboard View
│   │   ├── price_finder.html   # AI Price-Finder View
│   │   ├── expenses.html       # Expense Tracker View
│   │   └── copilot.html        # XAI Copilot Chat View
│   └── static/
│       ├── css/style.css
│       └── js/main.js
├── main.py                     # FastAPI Application Entrypoint
├── meika.db                    # SQLite Database (Auto-created on launch)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 🛠️ API Documentation

When the server is running, interactive OpenAPI documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
