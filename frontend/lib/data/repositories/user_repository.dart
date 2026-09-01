import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/user_profile.dart';

class UserRepository {
  final Dio _dio;

  UserRepository(this._dio);

  Future<UserProfile> getProfile() async {
    final response = await _dio.get('/users/me');
    return UserProfile.fromJson(response.data as Map<String, dynamic>);
  }

  Future<UserProfile> updatePreferredCurrency(String currencyCode) async {
    final response = await _dio.patch('/users/me', data: {'preferred_currency': currencyCode});
    return UserProfile.fromJson(response.data as Map<String, dynamic>);
  }
}

final userRepositoryProvider = Provider<UserRepository>((ref) {
  return UserRepository(ref.watch(dioProvider));
});
