# Meika — Flutter Client

Zen Garden-themed client for the Meika AI Financial Copilot. Talks to the FastAPI
backend in `../backend` over REST (`/api/v1`) and WebSocket (`/ws`).

## Prerequisites

- Flutter SDK 3.4+ ([install guide](https://docs.flutter.dev/get-started/install))
- The backend running locally (`docker compose up` from the repo root) or reachable
  over the network.

## Setup

```bash
flutter pub get
```

## Run

```bash
# Android emulator (default base URL already points at 10.0.2.2, the emulator's
# alias for the host machine's localhost)
flutter run

# iOS simulator / desktop / web — override the API host explicitly:
flutter run \
  --dart-define=MEIKA_API_BASE_URL=http://localhost:8000/api/v1 \
  --dart-define=MEIKA_WS_BASE_URL=ws://localhost:8000/ws

# Physical device — point at your machine's LAN IP instead of localhost.
```

### Signing in

Phase 8 JWT auth is live — the app opens on a login screen. Either register a
fresh account there ("New here? Create an account"), or log in with the
seeded dev account:

```bash
cd ../backend
python -m scripts.seed_dev_user
```

That prints the demo email/password to log in with (re-run it any time to
refresh the seeded expenses to "this month" — it's idempotent). The session
token is held in memory only (`authTokenProvider`) — there's no persistence
yet, so a page reload signs you back out.

The Price-Finder screen reads shared catalog data instead (not user-owned,
no login needed to search it), seeded separately:

```bash
cd ../backend
python -m scripts.seed_catalog
```

Set `SERPAPI_API_KEY` in `backend/.env` (free tier at [serpapi.com](https://serpapi.com),
100 searches/month, no card required) to search real, live products
worldwide instead of just the 5-item seed catalog — see the root README's
"Beyond the 8 phases" section for how the fallback works with no key set.

## Status

- App shell, navigation, and the Zen Garden theme (Phase 5) are wired up.
- Login screen (Phase 8) gates the app: register or log in against
  `POST /auth/register` / `POST /auth/login`, which return a JWT that a Dio
  interceptor attaches to every REST call and the Copilot WebSocket connects
  with (`?token=`). A logout button lives in the app bar.
- Dashboard and Budget screens (Phase 6) are live: Financial Clarity Score,
  budget snapshot, spending velocity/projection, category breakdown, and
  expense history — backed by `GET /dashboard/summary` and `GET /expenses`.
- Price-Finder screen (Phase 6) is live: search, per-store True Economic
  Cost comparison, computed price trend badges, and a recommendation banner
  that explains *why* — backed by `GET /price-finder/search`. With
  `SERPAPI_API_KEY` set, results are real live listings from anywhere in
  the world (a green "Live" badge marks these, with a "View listing" link
  to the real product) instead of the 5-item seed catalog — verified live
  in-browser with real Amazon.de/MediaMarkt/Target results.
- Copilot screen (Phase 7) is live: chat bubbles, a "Why?" panel per
  assistant reply showing the real computed factors behind it. Works out of
  the box with `GEMINI_API_KEY` unset (the backend falls back to a
  deterministic reply grounded in the same real numbers); set the key to get
  Gemini-phrased replies instead — that path hasn't been exercised against a
  real key yet.

**Known gap:** the JWT is in-memory only, so the app signs you out on every
restart. Verified end-to-end via curl/live-WebSocket against the real
backend and `flutter analyze`; the login flow itself hasn't been
screenshot-verified in-browser this session (a Browser-pane display issue,
not a known app defect) — give it a look before relying on it for a demo.

- **Add Expense** — a FAB on the Budget screen opens a form (title,
  category, amount, store, date, notes) posting to `POST /expenses`. Verified
  live in-browser.
- **Multi-currency display** — a currency chip in the app bar (e.g. "USD")
  opens a picker over every currency `GET /fx/rates` supports. Every KRW
  figure across Dashboard, Budget, and Price-Finder converts live using real
  exchange rates — verified live in-browser switching between USD/EUR/KRW.
  A fresh registration defaults to the device locale's currency
  (`WidgetsBinding.instance.platformDispatcher.locale`); login never
  silently overrides an existing choice. The Add Expense form also accepts
  "paid in a foreign currency" — toggle it, pick the currency, and the
  backend converts to KRW via a live rate at save time. The *prose* inside
  Financial Clarity Score factors, Price-Finder recommendations, and
  Copilot replies (all generated server-side) also renders in the
  signed-in user's currency now, not just the numeric fields around it —
  verified live in-browser.
