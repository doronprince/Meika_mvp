import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The current session's JWT, or null when signed out. In-memory only —
/// there's no persistence yet, so the app returns to the login screen on
/// restart. Read by the Dio interceptor (Authorization header) and the
/// WebSocket connection (?token= query param).
final authTokenProvider = StateProvider<String?>((ref) => null);
