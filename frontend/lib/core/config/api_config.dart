/// API endpoints, overridable per build via --dart-define.
///
/// Defaults target the Android emulator's alias for the host machine's
/// localhost (10.0.2.2). Override for iOS simulator, desktop, web, or a
/// physical device — see frontend/README.md.
class ApiConfig {
  ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'MEIKA_API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  static const String wsBaseUrl = String.fromEnvironment(
    'MEIKA_WS_BASE_URL',
    defaultValue: 'ws://10.0.2.2:8000/ws',
  );

  /// Interim tenant identity sent as `X-User-Id` until Phase 8 JWT auth
  /// lands (mirrors the backend's [[api/deps.py]] guardrail). Defaults to
  /// the fixed UUID `backend/scripts/seed_dev_user.py` seeds.
  static const String devUserId = String.fromEnvironment(
    'MEIKA_DEV_USER_ID',
    defaultValue: '00000000-0000-0000-0000-000000000001',
  );
}
