import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/exposure.dart';

class ExposureRepository {
  final Dio _dio;

  ExposureRepository(this._dio);

  Future<List<ExposureSessionEntry>> listSessions() async {
    final response = await _dio.get('/exposure/sessions');
    return (response.data as List).map((s) => ExposureSessionEntry.fromJson(s as Map<String, dynamic>)).toList();
  }

  Future<void> logSession({
    required DateTime occurredOn,
    required String platform,
    required ExposureKind kind,
    required int minutes,
    int? startedHour,
  }) async {
    await _dio.post('/exposure/sessions', data: {
      'occurred_on': occurredOn.toIso8601String().split('T').first,
      'platform': platform,
      'kind': kind.wireValue,
      'minutes': minutes,
      if (startedHour != null) 'started_hour': startedHour,
    });
  }

  Future<void> deleteSession(String id) async {
    await _dio.delete('/exposure/sessions/$id');
  }

  Future<ExposureInsightReport> fetchInsights() async {
    final response = await _dio.get('/exposure/insights');
    return ExposureInsightReport.fromJson(response.data as Map<String, dynamic>);
  }
}

final exposureRepositoryProvider = Provider<ExposureRepository>((ref) {
  return ExposureRepository(ref.watch(dioProvider));
});

final exposureSessionsProvider = FutureProvider.autoDispose<List<ExposureSessionEntry>>((ref) {
  return ref.watch(exposureRepositoryProvider).listSessions();
});

final exposureInsightsProvider = FutureProvider.autoDispose<ExposureInsightReport>((ref) {
  return ref.watch(exposureRepositoryProvider).fetchInsights();
});
