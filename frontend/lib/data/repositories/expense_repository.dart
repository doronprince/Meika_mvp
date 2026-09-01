import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/expense.dart';
import '../models/expense_category.dart';

class ExpenseRepository {
  final Dio _dio;

  ExpenseRepository(this._dio);

  Future<List<Expense>> listExpenses() async {
    final response = await _dio.get('/expenses');
    return (response.data as List)
        .map((e) => Expense.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Exactly one of (amountKrw) or (foreignAmount + foreignCurrency) must
  /// be provided — mirrors the backend's ExpenseCreate validator.
  Future<Expense> createExpense({
    required String title,
    required ExpenseCategory category,
    required DateTime occurredOn,
    double? amountKrw,
    double? foreignAmount,
    String? foreignCurrency,
    String? storeName,
    double transitCostKrw = 0,
    String transitMode = 'walk',
    String? notes,
  }) async {
    final response = await _dio.post('/expenses', data: {
      'title': title,
      'category': category.wireValue,
      if (amountKrw != null) 'amount_krw': amountKrw,
      if (foreignAmount != null) 'foreign_amount': foreignAmount,
      if (foreignCurrency != null) 'foreign_currency': foreignCurrency,
      if (storeName != null && storeName.isNotEmpty) 'store_name': storeName,
      'transit_cost_krw': transitCostKrw,
      'transit_mode': transitMode,
      'occurred_on': occurredOn.toIso8601String().split('T').first,
      if (notes != null && notes.isNotEmpty) 'notes': notes,
    });
    return Expense.fromJson(response.data as Map<String, dynamic>);
  }
}

final expenseRepositoryProvider = Provider<ExpenseRepository>((ref) {
  return ExpenseRepository(ref.watch(dioProvider));
});
