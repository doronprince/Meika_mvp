import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/claim_report.dart';

class ClaimRepository {
  final Dio _dio;

  ClaimRepository(this._dio);

  /// [stakeAmount] is in [stakeCurrency]; both optional.
  Future<ClaimReport> evaluate(String claimText, {double? stakeAmount, String? stakeCurrency}) async {
    final response = await _dio.post('/claim-check/evaluate', data: {
      'claim_text': claimText,
      if (stakeAmount != null) 'stake_amount': double.parse(stakeAmount.toStringAsFixed(2)),
      if (stakeAmount != null && stakeCurrency != null) 'stake_currency': stakeCurrency,
    });
    return ClaimReport.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<ClaimSummary>> history() async {
    final response = await _dio.get('/claim-check/history');
    return (response.data as List).map((h) => ClaimSummary.fromJson(h as Map<String, dynamic>)).toList();
  }

  Future<ClaimReport> fetch(String id) async {
    final response = await _dio.get('/claim-check/$id');
    return ClaimReport.fromJson(response.data as Map<String, dynamic>);
  }
}

final claimRepositoryProvider = Provider<ClaimRepository>((ref) {
  return ClaimRepository(ref.watch(dioProvider));
});

final claimHistoryProvider = FutureProvider.autoDispose<List<ClaimSummary>>((ref) {
  return ref.watch(claimRepositoryProvider).history();
});
