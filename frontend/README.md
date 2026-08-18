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

### Dev user identity

There's no login yet (Phase 8 JWT auth is still pending), so every API call
sends a fixed `X-User-Id` header — see `ApiConfig.devUserId`. It defaults to
the UUID `backend/scripts/seed_dev_user.py` seeds:

```bash
cd ../backend
python -m scripts.seed_dev_user
```

Run that once against your local Postgres before using the Dashboard or
Budget screens, or you'll hit a 404 (no matching user). Override the id with
`--dart-define=MEIKA_DEV_USER_ID=<uuid>` to point at a different seeded user.

The Price-Finder screen reads shared catalog data instead (not user-owned),
seeded separately:

```bash
cd ../backend
python -m scripts.seed_catalog
```

## Status

- App shell, navigation, and the Zen Garden theme (Phase 5) are wired up.
- Dashboard and Budget screens (Phase 6) are live: Financial Clarity Score,
  budget snapshot, spending velocity/projection, category breakdown, and
  expense history — backed by `GET /dashboard/summary` and `GET /expenses`.
- Price-Finder screen (Phase 6) is live: search, per-store True Economic
  Cost comparison, computed price trend badges, and a recommendation banner
  that explains *why* — backed by `GET /price-finder/search`.
- Copilot screen is still a placeholder — needs the Phase 4/7 Gemini
  WebSocket integration.
