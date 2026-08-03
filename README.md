# Meika (명가) — AI Financial Copilot

> **Tagline:** Spend Savvy. Live Fully.
> **Brand Identity:** Zen Garden minimalism — Washi `#FBFBF7`, Sumi `#2F2F2F`, Matcha `#889A7B`.
> **Target Audience:** International students in Seoul & global campuses navigating financial anxiety.

Meika is an Explainable AI (XAI) financial copilot. It never gives a financial
directive without rendering the data-driven reasoning behind it. This repo is
a decoupled monorepo: a FastAPI JSON/WebSocket backend and a Flutter client.

---

## Architecture

```text
Meika_mvp/
├── backend/           FastAPI API (PostgreSQL, SQLAlchemy, Alembic)
├── frontend/           Flutter client (Zen Garden design system)
├── docker-compose.yml  Postgres + backend, for local dev
└── .env.example        Copy to .env at repo root before running docker compose
```

- **Backend:** Python / FastAPI, async SQLAlchemy 2.0, PostgreSQL, Alembic migrations.
- **Frontend:** Flutter (Dart), Zen Garden theme, Figtree via `google_fonts`.
- **AI/XAI layer:** Gemini-backed "Wise Guide" copilot (wired in Phase 4) — every
  recommendation ships with the computed factors behind it, never a bare directive.
- **Communication:** REST JSON (`/api/v1/...`) + WebSocket (`/ws/...` for the copilot chat).

## Quickstart

### Backend + Postgres (Docker)

```bash
cp .env.example .env   # fill in POSTGRES_PASSWORD and GEMINI_API_KEY
docker compose up --build
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health — reports `{"status": "ok", "database": "ok" | "unreachable"}`

### Backend only (no Docker)

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
cp ../.env.example .env   # or export the same vars into your shell
uvicorn app.main:app --reload
pytest
```

### Frontend (Flutter)

```bash
cd frontend
flutter pub get
flutter run --dart-define=MEIKA_API_BASE_URL=http://localhost:8000/api/v1
```

See `frontend/README.md` for platform-specific API host overrides (Android
emulator vs. iOS simulator vs. physical device).

---

## Build Phases

- [x] **Phase 1** — Project scaffold: FastAPI backend structure, Postgres Docker
      Compose, Flutter frontend init.
- [ ] Phase 2 — Database schema, SQLAlchemy models, Alembic migrations (with
      tenant-scoped `user_id` on every owned table from the first revision).
- [ ] Phase 3 — Core backend logic: Price-Finder / True Economic Cost engine,
      spending velocity, Financial Clarity Score.
- [ ] Phase 4 — API routing + XAI Copilot WebSocket integration (Gemini).
- [ ] Phase 5 — Frontend Zen Garden design system (theme, typography, colors).
- [ ] Phase 6 — Frontend dashboard & predictive budgeting UI.
- [ ] Phase 7 — Frontend XAI Copilot chat UI with reasoning panels.
- [ ] Phase 8 — Security review, JWT auth, API rate limiting.

## Guardrails

- **Tenant isolation:** every user-owned table carries `user_id`; every query
  is scoped through it. No cross-tenant reads, ever.
- **No hardcoded secrets:** `.env` is gitignored; `.env.example` documents the
  shape only.
- **XAI enforcement:** every "Buy" / "Wait" / budget directive from the
  copilot renders alongside the specific computed factors that produced it —
  no fabricated reasoning strings.
