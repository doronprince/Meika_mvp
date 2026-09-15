import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models/income_stream.dart';
import '../data/models/survival_report.dart';
import '../data/repositories/survival_repository.dart';

final incomeStreamsProvider = FutureProvider.autoDispose<List<IncomeStream>>((ref) {
  return ref.watch(survivalRepositoryProvider).listIncomeStreams();
});

final shockPresetsProvider = FutureProvider.autoDispose<List<ShockPreset>>((ref) {
  return ref.watch(survivalRepositoryProvider).fetchPresets();
});

/// Keyed by the JSON-encoded request, so an identical scenario reuses one
/// response and any change (a toggled shock, a slider released) re-runs it.
final survivalReportProvider = FutureProvider.autoDispose.family<SurvivalReport, String>((ref, requestJson) {
  return ref.watch(survivalRepositoryProvider).simulate(jsonDecode(requestJson) as Map<String, dynamic>);
});
