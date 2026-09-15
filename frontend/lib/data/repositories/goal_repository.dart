import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/expense_category.dart';
import '../models/goal.dart';

String _isoDate(DateTime d) => d.toIso8601String().split('T').first;

/// Amounts go over the wire as 2-decimal strings: the backend validates them
/// as Decimal(max_digits=12, decimal_places=2), which a raw double like
/// 1234.5600000001 would fail.
String _money(double krw) => krw.toStringAsFixed(2);

class GoalRepository {
  final Dio _dio;

  GoalRepository(this._dio);

  Future<List<Goal>> listGoals() async {
    final response = await _dio.get('/goals');
    return (response.data as List).map((g) => Goal.fromJson(g as Map<String, dynamic>)).toList();
  }

  Future<Goal> createGoal({
    required String name,
    required GoalType goalType,
    required double targetAmountKrw,
    required DateTime targetDate,
    double startingAmountKrw = 0,
    ExpenseCategory? category,
  }) async {
    final response = await _dio.post('/goals', data: {
      'name': name,
      'goal_type': goalType.wireValue,
      'target_amount_krw': _money(targetAmountKrw),
      if (goalType == GoalType.savings && startingAmountKrw > 0) 'starting_amount_krw': _money(startingAmountKrw),
      if (goalType == GoalType.spendingCap && category != null) 'category': category.wireValue,
      'target_date': _isoDate(targetDate),
    });
    return Goal.fromJson(response.data as Map<String, dynamic>);
  }

  /// Negative [amountKrw] records a withdrawal.
  Future<Goal> addContribution(String goalId, double amountKrw) async {
    final response = await _dio.post('/goals/$goalId/contributions', data: {'amount_krw': _money(amountKrw)});
    return Goal.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> deleteGoal(String goalId) async {
    await _dio.delete('/goals/$goalId');
  }
}

final goalRepositoryProvider = Provider<GoalRepository>((ref) {
  return GoalRepository(ref.watch(dioProvider));
});
