import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth/auth_token_provider.dart';
import '../data/models/auth_result.dart';
import '../data/repositories/auth_repository.dart';

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
      _submit(() => _repo.register(email: email, password: password));

  Future<void> _submit(Future<AuthResult> Function() action) async {
    state = const AuthFormState(isSubmitting: true);
    try {
      final result = await action();
      _ref.read(authTokenProvider.notifier).state = result.accessToken;
      state = const AuthFormState();
    } catch (e) {
      state = AuthFormState(error: e.toString());
    }
  }
}

final authControllerProvider = StateNotifierProvider.autoDispose<AuthController, AuthFormState>((ref) {
  return AuthController(ref.watch(authRepositoryProvider), ref);
});
