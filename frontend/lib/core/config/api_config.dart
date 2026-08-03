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
}
