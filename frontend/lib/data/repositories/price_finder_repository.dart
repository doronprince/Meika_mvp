import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/price_finder_result.dart';

class PriceFinderRepository {
  final Dio _dio;

  PriceFinderRepository(this._dio);

  Future<List<PriceFinderResult>> search(String query) async {
    final response = await _dio.get(
      '/price-finder/search',
      queryParameters: query.isEmpty ? null : {'q': query},
    );
    return (response.data as List)
        .map((r) => PriceFinderResult.fromJson(r as Map<String, dynamic>))
        .toList();
  }
}

final priceFinderRepositoryProvider = Provider<PriceFinderRepository>((ref) {
  return PriceFinderRepository(ref.watch(dioProvider));
});
