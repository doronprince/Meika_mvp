import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/compliance_foresight.dart';

String _money(double krw) => krw.toStringAsFixed(2);

class ComplianceRepository {
  final Dio _dio;

  ComplianceRepository(this._dio);

  Future<ComplianceForesight> fetchForesight() async {
    final response = await _dio.get('/compliance/foresight');
    return ComplianceForesight.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<ComplianceRuleView>> fetchRules() async {
    final response = await _dio.get('/compliance/rules');
    return (response.data as List).map((r) => ComplianceRuleView.fromJson(r as Map<String, dynamic>)).toList();
  }

  Future<ComplianceSettings> fetchSettings() async {
    final response = await _dio.get('/compliance/settings');
    return ComplianceSettings.fromJson(response.data as Map<String, dynamic>);
  }

  Future<ComplianceSettings> updateSettings({String? residenceJurisdiction, required int startMonth, required int startDay}) async {
    final response = await _dio.put('/compliance/settings', data: {
      if (residenceJurisdiction != null && residenceJurisdiction.isNotEmpty) 'residence_jurisdiction': residenceJurisdiction,
      'fiscal_year_start_month': startMonth,
      'fiscal_year_start_day': startDay,
    });
    return ComplianceSettings.fromJson(response.data as Map<String, dynamic>);
  }

  /// Your own figure for a rule. Marks it as set by you.
  Future<void> setThreshold(String ruleKey, double thresholdKrw) async {
    await _dio.put('/compliance/rules/$ruleKey/override', data: {'threshold_amount_krw': _money(thresholdKrw)});
  }

  /// Records that you checked the current figure with a professional.
  Future<void> markVerified(String ruleKey, {String? note}) async {
    await _dio.put('/compliance/rules/$ruleKey/override', data: {
      'assumption_source': 'user_verified',
      if (note != null && note.isNotEmpty) 'verified_note': note,
    });
  }

  Future<void> setEnabled(String ruleKey, bool enabled) async {
    await _dio.put('/compliance/rules/$ruleKey/override', data: {'is_enabled': enabled});
  }

  /// Back to Meika's packaged, unverified default.
  Future<void> resetRule(String ruleKey) async {
    await _dio.delete('/compliance/rules/$ruleKey/override');
  }

  Future<void> setReceipt(String expenseId, {required bool hasReceipt}) async {
    await _dio.post('/compliance/annotations', data: {'expense_id': expenseId, 'has_documentation': hasReceipt});
  }
}

final complianceRepositoryProvider = Provider<ComplianceRepository>((ref) {
  return ComplianceRepository(ref.watch(dioProvider));
});

final complianceForesightProvider = FutureProvider.autoDispose<ComplianceForesight>((ref) {
  return ref.watch(complianceRepositoryProvider).fetchForesight();
});

final complianceRulesProvider = FutureProvider.autoDispose<List<ComplianceRuleView>>((ref) {
  return ref.watch(complianceRepositoryProvider).fetchRules();
});

final complianceSettingsProvider = FutureProvider.autoDispose<ComplianceSettings>((ref) {
  return ref.watch(complianceRepositoryProvider).fetchSettings();
});
