import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth/auth_token_provider.dart';
import '../data/models/auth_result.dart';
import '../data/repositories/auth_repository.dart';
import '../data/repositories/user_repository.dart';
import 'currency_providers.dart';

class AuthFormState {
  final bool isSubmitting;
  final String? error;

  const AuthFormState({this.isSubmitting = false, this.error});
}

class AuthController extends StateNotifier<AuthFormState> {
  final AuthRepository _repo;
  final Ref _ref;

  AuthController(this._repo, this._ref) : super(const AuthFormState());

  Future<void> login(String email, String password) =>
      _submit(() => _repo.login(email: email, password: password));

  Future<void> register(String email, String password) =>
      _submit(() => _repo.register(email: email, password: password), isNewAccount: true);

  Future<void> _submit(Future<AuthResult> Function() action, {bool isNewAccount = false}) async {
    state = const AuthFormState(isSubmitting: true);
    try {
      final result = await action();
      _ref.read(authTokenProvider.notifier).state = result.accessToken;

      if (isNewAccount) {
        // Best-effort: default a fresh account's display currency to the
        // device's region. Never applied on login, so an existing user's
        // choice — even if it's still the server default of KRW — is never
        // silently overridden.
        final deviceCurrency = _ref.read(deviceCurrencyProvider);
        if (deviceCurrency != 'KRW') {
          try {
            await _ref.read(userRepositoryProvider).updatePreferredCurrency(deviceCurrency);
          } catch (_) {
            // Non-fatal — the user can still set it manually.
          }
        }
      }

      state = const AuthFormState();
    } catch (e) {
      state = AuthFormState(error: e.toString());
    }
  }
}

final authControllerProvider = StateNotifierProvider.autoDispose<AuthController, AuthFormState>((ref) {
  return AuthController(ref.watch(authRepositoryProvider), ref);
});
