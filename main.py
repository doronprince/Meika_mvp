import uvicorn
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import init_db
from app.routers import price_router, expense_router, copilot_router, dashboard_router

app = FastAPI(
    title="Meika AI Financial Copilot",
    description="Zen Minimalist Financial Copilot & Price-Finder MVP for International Students",
    version="1.0.0"
)

# Initialize Database
@app.on_event("startup")
def on_startup():
    init_db()

# Mount Static Files and Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "app", "static")
templates_dir = os.path.join(BASE_DIR, "app", "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Include Routers
app.include_router(dashboard_router.router)
app.include_router(price_router.router)
app.include_router(expense_router.router)
app.include_router(copilot_router.router)

# Page Routes
@app.get("/")
def render_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "page": "dashboard"})

@app.get("/price-finder")
def render_price_finder(request: Request):
    return templates.TemplateResponse("price_finder.html", {"request": request, "page": "price_finder"})

@app.get("/expenses")
def render_expenses(request: Request):
    return templates.TemplateResponse("expenses.html", {"request": request, "page": "expenses"})

@app.get("/copilot")
def render_copilot(request: Request):
    return templates.TemplateResponse("copilot.html", {"request": request, "page": "copilot"})

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
