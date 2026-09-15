import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/income_stream.dart';
import '../models/survival_report.dart';

/// Rounds to 2 decimal places — the backend validates money fields with
/// decimal_places=2, and a converted double like 1234.5678 would be a 422.
double _money(double value) => double.parse(value.toStringAsFixed(2));

class SurvivalRepository {
  final Dio _dio;

  SurvivalRepository(this._dio);

  Future<List<IncomeStream>> listIncomeStreams() async {
    final response = await _dio.get('/income-streams');
    return (response.data as List).map((e) => IncomeStream.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<IncomeStream> createIncomeStream({
    required String label,
    required IncomeKind kind,
    required double monthlyAmount,
    required String currency,
  }) async {
    final response = await _dio.post('/income-streams', data: {
      'label': label,
      'kind': kind.wireValue,
      'monthly_amount': _money(monthlyAmount),
      'currency': currency,
    });
    return IncomeStream.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteIncomeStream(String id) async {
    await _dio.delete('/income-streams/$id');
  }

  /// `null` clears it — the backend treats "not set" differently from zero.
  Future<void> setLiquidSavings(double? krw) async {
    await _dio.patch('/users/me', data: {'liquid_savings_krw': krw == null ? null : _money(krw)});
  }

  Future<List<ShockPreset>> fetchPresets() async {
    final response = await _dio.get('/survival/presets');
    return (response.data as List).map((p) => ShockPreset.fromJson(p as Map<String, dynamic>)).toList();
  }

  Future<SurvivalReport> simulate(Map<String, dynamic> request) async {
    final response = await _dio.post('/survival/simulate', data: request);
    return SurvivalReport.fromJson(response.data as Map<String, dynamic>);
  }
}

final survivalRepositoryProvider = Provider<SurvivalRepository>((ref) {
  return SurvivalRepository(ref.watch(dioProvider));
});
