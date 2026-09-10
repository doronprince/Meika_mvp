# Meika — Phase-I Review 1 Q&A Prep
**Project:** Explainable AI-Based Personal Financial Copilot for Predictive Budgeting, Goal Forecasting, and Financial Risk Analysis
**Review date:** 14 Aug 2026
**Base paper:** Bhavik Pathak, "A Survey of the Comparison Shopping Agent-Based Decision Support Systems," *Journal of Electronic Commerce Research*, Vol 11 No 3, 2010

---

## 1. Have you finalized the architecture?

Yes. Meika is built as a **decoupled monorepo**:

- **Backend** — Python / FastAPI, async SQLAlchemy 2.0, PostgreSQL, Alembic migrations. Internally layered `routers → services → models` (routers handle HTTP/WebSocket I/O, services hold business logic, models are the SQLAlchemy ORM/schema layer).
- **Frontend** — Flutter (Dart) client using a custom "Zen Garden" design system (Washi/Sumi/Matcha palette, Figtree typography).
- **Communication** — REST JSON under `/api/v1/...` for CRUD and dashboard data, plus a WebSocket channel (`/ws/...`) reserved for the live XAI copilot chat.
- **AI/XAI layer** — a Gemini-backed "Wise Guide" conversational layer that will sit on top of deterministic, auditable financial calculations rather than a black-box model (see Q2).

This backend/frontend split, the four-layer module boundary (data → models/analysis → interface → user customization), and the communication protocol are settled and match the four-component Decision Support System framework from the chosen base paper (Pathak, 2010): **data component** (Postgres transactional store + Seoul retail catalog reference data), **model component** (deterministic analytics + LLM reasoning), **interface component** (Flutter UI + conversational chat), **user-customization component** (per-user budget threshold, strict tenant isolation via `user_id`).

What is *not* finalized yet is the wiring of two pieces into that architecture — the Gemini WebSocket copilot (Phase 4/7) and JWT auth/rate-limiting (Phase 8). The shape of the architecture itself does not change to add these; they slot into the existing router/service layers.

---

## 2. Justify the selection of methods/components

| Component | Choice | Justification |
|---|---|---|
| API framework | FastAPI | Native async support (needed for concurrent DB + LLM calls), automatic OpenAPI docs, Pydantic-based request/response validation — reduces bugs in a financial-data API. |
| Database | PostgreSQL + async SQLAlchemy 2.0 + Alembic | Relational integrity and ACID guarantees matter for monetary data; Alembic gives versioned, reviewable schema migrations across the project's multiple review cycles. |
| Frontend | Flutter | Single codebase for mobile + web, which matches the target user (international students who mostly use a phone), and made it feasible to build a fully custom design system (Zen Garden) within project time constraints. |
| Conversational layer | Gemini LLM | Used only for *natural-language explanation generation*, not for the underlying financial computation — keeps the LLM's role bounded and auditable, and is more cost-effective for a student project than GPT-4-class APIs. |
| Core analytics method | Deterministic, rule-based scoring (not a trained ML model) | This is the key methodological decision: the Financial Clarity Score is computed from three explicit, hand-specified factors (pace-vs-budget, projected month-end overage, category concentration), each penalty formula is fixed and auditable, and every factor is emitted as a structured `XAIFactor {label, detail, value}` object. This was chosen deliberately over a black-box model + post-hoc explanation (e.g., SHAP/LIME), because the base paper's and the proposal's core gap is "AI recommendations without transparent reasoning" — a system that is explainable *by construction* closes that gap more directly than a complex model that needs a separate explanation layer bolted on. |
| Tenant isolation | `user_id` on every owned table, enforced at the query layer | Required because this is a shared multi-user financial system; prevents cross-tenant data leakage, which is a baseline security/trust requirement for any real financial app. |

---

## 3. What modules are selected?

1. **Expense & Income Management** — CRUD for user transactions (`models/expense.py`, `routers/expense.py`, `services/expense_service.py`), tagged by category, store, and transit mode/cost.
2. **Predictive Budgeting (Spending Velocity & Projection)** — computes daily spending velocity and projects month-end spend/overage from the current trend (`services/dashboard_service.py`).
3. **Financial Clarity Score (Explainable Risk Scoring)** — the composite XAI risk module: combines pace, projection, and category-concentration penalties into a single 0–100 score with a Low/Moderate/High risk label and the underlying factors attached.
4. **Price-Finder / True Economic Cost Engine** *(in progress)* — compares a product's price plus transit cost across stores and derives a rising/falling/stable price trend from historical price observations. Data model (`Store`, `Product`, `ProductListing`, `PriceQuote`) is already scaffolded; the comparison service and the underlying Seoul retail catalog data are not built yet — this is the main open item for Phase 3.
5. **XAI Copilot Chat** *(in progress)* — Gemini-backed conversational assistant; `ChatMessage` model already stores structured `xai_factors` JSON per assistant turn so replies stay traceable to computed factors rather than being free-form; the live Gemini/WebSocket wiring is Phase 4/7 work.
6. **User & Tenant Management** — account, monthly budget threshold, and the tenant-isolation guardrail applied across every owned table.

On the frontend, this maps to: a completed **Dashboard screen** (Clarity Score, budget snapshot, velocity/projection, category breakdown) and **Budget screen** (cash-flow risk outlook, expense history), plus placeholder **Price-Finder** and **Copilot chat** screens waiting on modules 4 and 5.

---

## 4. What dataset is used? *(flag this before the review — see note below)*

Be precise and honest here rather than overclaiming a dataset that isn't really there yet:

- **Primary data source (in use today):** user-generated transactional data — expenses logged through the app (`Expense` table: title, category, amount, store, transit cost/mode, date). All predictive budgeting and Clarity Score calculations run on this live, per-user operational data. This is *not* a static training dataset — it's the input data the deterministic analytics operate on.
- **Secondary data source (modeled, not populated):** a "Seoul retail catalog" reference dataset (`Store`, `Product`, `ProductListing`, `PriceQuote` tables) intended to power the Price-Finder engine. The schema exists but currently has **no seeded data** — this is a real gap.
- **No public ML benchmark dataset is currently wired into the project**, because the core analytics (spending velocity, projection, clarity score) are intentionally rule-based rather than model-trained (see Q2's justification for explainability-by-construction).

**Recommendation before your review:** decide how you want to frame this if asked directly. Two honest options:
1. State plainly that the project's predictive components are deterministic/statistical (not supervised-ML) by design, for explainability, and that no training dataset is needed for the modules built so far — reserve "dataset" language for the Price-Finder catalog.
2. If the panel expects a concrete dataset, source and seed a small Seoul retail-price dataset (even synthetic/manually curated for a few dozen products/stores) before tomorrow to back the Price-Finder claim, and optionally cite a public personal-finance transactions dataset (e.g., a Kaggle household-expenses dataset) as what a future ML-based spend-forecasting extension would train on.

I can generate a synthetic seed dataset for the Seoul catalog tables right now if you want something concrete to point to tomorrow — say the word and I'll build it.

---

## 5. Have you got 20% implementation results for the project?

Yes, and it's demoable, not just described. Evidence from the actual codebase:

- **Backend, live and tested:** `GET /api/v1/health`, `/api/v1/expenses` (CRUD), `/api/v1/dashboard/summary` are all implemented and covered by automated tests (`test_health.py`, `test_expenses.py`, `test_dashboard.py`). Database schema is real — two Alembic migrations already applied (`f3a9c1d2b6e0_initial_schema`, `b7d4e8f1a2c3_drop_listing_transit_columns`), so the "DB schema not started" line in the README's phase checklist is stale — schema, models, and migrations are in fact done.
- **Frontend, live and wired to the API:** Dashboard screen and Budget screen are fully built (`dashboard_screen.dart`, `budget_screen.dart`, ~7–11 KB each with real widgets, providers, and repositories talking to the live endpoints), on top of the completed Zen Garden theme system.
- **Not yet built:** Price-Finder screen and Copilot chat screen are stub "coming soon" placeholders; Gemini WebSocket integration and JWT auth are not started.

In terms of the 8-phase build plan: Phase 1 (scaffold) and Phase 5 (design system) are fully complete, Phase 3 (core backend analytics) and Phase 6 (frontend dashboard/budgeting UI) are roughly half done with the harder, novel part (the explainable Clarity Score) already live, and Phase 2 (DB schema) is further along than the README currently shows. That's a reasonable, defensible ~20% of total project scope with a working, demoable slice — the pace/projection/clarity-score explainability, which is the project's actual research contribution, is exactly the part that's live.

**Before the review:** update the README's Phase 2 checkbox to reflect that the schema/migrations are done — right now it understates your own progress.
