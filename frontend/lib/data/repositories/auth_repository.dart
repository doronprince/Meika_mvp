import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_error.dart';
import '../models/auth_result.dart';

class AuthException implements Exception {
  final String message;
  const AuthException(this.message);

  @override
  String toString() => message;
}

/// Turns a failed sign-in or sign-up into something true and actionable.
///
/// The server's own reason comes first: a rejected address or password is a
/// 422 whose `detail` is a *list* of validation errors, and reporting that as
/// "could not reach the server" sends people to check their wifi over a typo.
/// Only a request that genuinely never got an answer says so.
String authErrorMessage(DioException error) {
  final response = error.response;
  if (response != null) {
    final message = apiErrorMessage(error);
    if (response.statusCode == 429) {
      return 'Too many attempts — wait a moment and try again.';
    }
    if (message.toLowerCase().contains('not a valid email address')) {
      return 'That email address looks incomplete — it needs a domain with a dot, like name@example.com.';
    }
    return message;
  }
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.sendTimeout:
      return 'The server took too long to answer. It sleeps when idle and can need a minute to wake — try again.';
    default:
      return 'Could not reach the server. Check your connection and try again.';
  }
}

class AuthRepository {
  final Dio _dio;

  AuthRepository(this._dio);

  Future<AuthResult> register({required String email, required String password}) {
    return _submit('/auth/register', email: email, password: password);
  }

  Future<AuthResult> login({required String email, required String password}) {
    return _submit('/auth/login', email: email, password: password);
  }

  Future<AuthResult> _submit(String path, {required String email, required String password}) async {
    try {
      final response = await _dio.post(path, data: {'email': email, 'password': password});
      return AuthResult.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw AuthException(authErrorMessage(e));
    }
  }
}

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(ref.watch(dioProvider));
});
