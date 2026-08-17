import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../models/expense.dart';

class ExpenseRepository {
  final Dio _dio;

  ExpenseRepository(this._dio);

  Future<List<Expense>> listExpenses() async {
    final response = await _dio.get('/expenses');
    return (response.data as List)
        .map((e) => Expense.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}

final expenseRepositoryProvider = Provider<ExpenseRepository>((ref) {
  return ExpenseRepository(ref.watch(dioProvider));
});
