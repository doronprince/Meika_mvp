import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/expense_category.dart';

class FxRepository {
  final Dio _dio;

  FxRepository(this._dio);

  /// Live rates FROM `base` TO every other supported currency.
  Future<Map<String, double>> getRates({String base = 'KRW'}) async {
    final response = await _dio.get('/fx/rates', queryParameters: {'base': base});
    final rates = (response.data as Map<String, dynamic>)['rates'] as Map<String, dynamic>;
    return rates.map((code, value) => MapEntry(code, parseAmount(value)));
  }
}

final fxRepositoryProvider = Provider<FxRepository>((ref) {
  return FxRepository(ref.watch(dioProvider));
});
