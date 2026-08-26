import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/auth_result.dart';

class AuthException implements Exception {
  final String message;
  const AuthException(this.message);

  @override
  String toString() => message;
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
      final detail = e.response?.data is Map ? (e.response?.data as Map)['detail'] : null;
      if (detail is String) throw AuthException(detail);
      if (e.response?.statusCode == 429) {
        throw const AuthException('Too many attempts — wait a moment and try again.');
      }
      throw const AuthException('Could not reach the server. Check your connection and try again.');
    }
  }
}

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(ref.watch(dioProvider));
});
