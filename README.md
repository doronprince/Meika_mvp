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
- Every other endpoint needs a real account now (Phase 8): register via
  `POST /auth/register` (or use the Flutter app's sign-up form), or seed one
  with `python -m scripts.seed_dev_user` from `backend/` — see
  `frontend/README.md` for the demo credentials it prints.

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
- [x] Phase 3 — Core backend logic: Price-Finder / True Economic Cost engine,
      spending velocity, Financial Clarity Score.
  - [x] Spending velocity, predictive month-end projection, and an
        explainable Financial Clarity Score — `GET /dashboard/summary`.
  - [x] Price-Finder / True Economic Cost engine — `GET /price-finder/search`
        compares real sticker price against price + transit cost across
        Seoul retailers, with a computed (never asserted) rising/falling/
        stable price trend per listing. Seed data: `scripts/seed_catalog.py`.
- [x] Phase 4 — API routing + XAI Copilot WebSocket integration (Gemini).
  - [x] `ws://.../ws/copilot?token=<jwt>` — every reply is grounded in
        real computed numbers (Financial Clarity Score factors or a
        Price-Finder recommendation), never fabricated, whether or not
        Gemini is configured. Chat history persists via `ChatMessage` and
        is readable over `GET /copilot/history`.
  - [x] Deterministic fallback reply path — fully tested, this is what runs
        with `GEMINI_API_KEY` unset (the default in `.env.example`).
  - [ ] **Not verified**: the live Gemini call path (`google-genai`). It's
        implemented and wrapped so any failure falls back to the
        deterministic path, but nobody has run it against a real API key
        yet — set `GEMINI_API_KEY` and try a request before trusting it.
- [x] Phase 5 — Frontend Zen Garden design system (theme, typography, colors).
- [x] Phase 6 — Frontend dashboard & predictive budgeting UI.
  - [x] Dashboard screen: Financial Clarity Score, budget snapshot,
        velocity/projection, category breakdown.
  - [x] Budget screen: cash-flow risk outlook, expense history.
  - [x] Price-Finder screen: search, per-store True Economic Cost
        comparison, price trend badges, computed recommendation banner.
- [x] Phase 7 — Frontend XAI Copilot chat UI with reasoning panels.
  - [x] Copilot screen: chat bubbles, an expandable "Why?" panel per
        assistant reply showing the real computed factors behind it,
        connection/error states. Verified end-to-end over a live WebSocket
        connection against the running backend; not yet screenshot-verified
        in-browser (tooling issue this session, not a known app defect).
- [x] Phase 8 — Security review, JWT auth, API rate limiting.
  - [x] `POST /auth/register` and `POST /auth/login` issue a signed JWT
        (`bcrypt` password hashing, `pyjwt` signing). `get_current_user_id`
        now requires a valid `Authorization: Bearer` token everywhere — the
        interim `X-User-Id` header is gone, including on the WebSocket
        (`?token=` query param, since a browser WS handshake can't carry a
        custom header).
  - [x] In-memory sliding-window rate limiting (`app/core/rate_limit.py`) —
        60 req/min general, 10 req/min on `/auth/*`. Per-process only, see
        the module docstring — swap for Redis before running >1 worker.
  - [ ] **Not a full security review.** This covers auth + rate limiting
        only: no HTTPS enforcement, no refresh-token/token-revocation flow,
        no brute-force lockout beyond the rate limit, and the frontend
        token is in-memory only (signing out on every app restart — no
        secure storage yet). Treat this as a solid MVP baseline, not an
        audit sign-off.

## Beyond the 8 phases

- [x] **Manual expense entry** — an Add Expense screen (FAB on Budget) wired
      to the existing `POST /expenses`, so real spending replaces the seed
      script as the source of truth for a signed-in user.
- [x] **Multi-currency** — `GET /fx/rates` serves live rates (ECB via
      api.frankfurter.dev, 1hr cache). Every amount is still *stored* in
      KRW (source of truth); display converts to the signed-in user's
      `preferred_currency` (`GET/PATCH /users/me`), defaulted from device
      locale on first registration, overridable any time via the currency
      picker in the app bar. Log an expense in a foreign currency and the
      backend snapshots the live rate at entry time (`expenses.original_currency`
      / `original_amount`) so a past expense's KRW value never drifts as
      rates move later.
  - Known gap: the Financial Clarity Score / Price-Finder recommendation
    *prose* (the XAI factor `detail` text) still quotes KRW verbatim, since
    it's generated server-side from the real computation — only the
    numeric display fields around it convert. Fixing that means either
    generating that prose per-currency or converting inline within it;
    out of scope for this pass.
- [ ] **Real payment processing** — explicitly not built with raw
      card/account storage under any circumstance (a PCI-DSS violation
      waiting to happen). The only path is a real processor (Stripe or
      similar) with proper tokenization, which needs the project owner's
      own test-mode API keys — blocked pending that.

## Guardrails

- **Tenant isolation:** every user-owned table carries `user_id`; every query
  is scoped through it. No cross-tenant reads, ever.
- **No hardcoded secrets:** `.env` is gitignored; `.env.example` documents the
  shape only. `JWT_SECRET_KEY` boots with an insecure dev default if unset —
  never rely on that outside local development.
- **XAI enforcement:** every "Buy" / "Wait" / budget directive from the
  copilot renders alongside the specific computed factors that produced it —
  no fabricated reasoning strings.
