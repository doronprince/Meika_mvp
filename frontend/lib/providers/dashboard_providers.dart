import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models/dashboard_summary.dart';
import '../data/models/expense.dart';
import '../data/repositories/dashboard_repository.dart';
import '../data/repositories/expense_repository.dart';

final dashboardSummaryProvider = FutureProvider.autoDispose<DashboardSummary>((ref) {
  return ref.watch(dashboardRepositoryProvider).fetchSummary();
});

final expenseListProvider = FutureProvider.autoDispose<List<Expense>>((ref) {
  return ref.watch(expenseRepositoryProvider).listExpenses();
});
