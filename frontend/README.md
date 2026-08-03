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

## Status

Phase 1 scaffold: app shell, navigation, and the Zen Garden theme are wired up.
Dashboard, Price-Finder, Budget, and Copilot screens are placeholders pending
Phases 5–7.
