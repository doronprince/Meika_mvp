import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/dashboard_summary.dart';
import '../data/models/expense.dart';
import '../data/models/expense_category.dart';
import '../providers/currency_providers.dart';
import '../providers/dashboard_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';
import 'add_expense_screen.dart';

class BudgetScreen extends ConsumerWidget {
  const BudgetScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(dashboardSummaryProvider);
    final expenses = ref.watch(expenseListProvider);

    return Scaffold(
      floatingActionButton: FloatingActionButton(
        backgroundColor: ZenColors.matcha,
        foregroundColor: Colors.white,
        onPressed: () async {
          final saved = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => const AddExpenseScreen()),
          );
          if (saved == true) {
            ref.invalidate(dashboardSummaryProvider);
            ref.invalidate(expenseListProvider);
          }
        },
        child: const Icon(Icons.add_rounded),
      ),
      body: RefreshIndicator(
        color: ZenColors.matcha,
        onRefresh: () async {
          ref.invalidate(dashboardSummaryProvider);
          ref.invalidate(expenseListProvider);
        },
        child: AsyncValueView<DashboardSummary>(
          value: summary,
          onRetry: () => ref.invalidate(dashboardSummaryProvider),
          builder: (context, data) => BoundedContent(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 88),
              children: [
                _CashFlowRiskCard(summary: data),
                const SizedBox(height: 16),
                Text('Expense History', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                AsyncValueView<List<Expense>>(
                  value: expenses,
                  onRetry: () => ref.invalidate(expenseListProvider),
                  builder: (context, items) => _ExpenseHistoryList(expenses: items),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CashFlowRiskCard extends ConsumerWidget {
  final DashboardSummary summary;

  const _CashFlowRiskCard({required this.summary});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = RiskColors.forLevel(summary.clarityScore.riskLevel);
    final velocity = summary.spendingVelocityKrwPerDay;
    final remaining = summary.remainingBudgetKrw;
    String money(num v) => formatKrwForDisplay(ref, v);

    String outlook;
    if (remaining <= 0) {
      outlook = 'Monthly budget already exceeded by ${money(-remaining)}.';
    } else if (velocity <= 0) {
      outlook = 'No spending recorded yet — budget fully available.';
    } else {
      final daysLeft = (remaining / velocity).floor();
      final exhaustionDate = DateTime.now().add(Duration(days: daysLeft));
      final withinMonth = exhaustionDate.month == DateTime.now().month;
      outlook = withinMonth
          ? 'At this pace, the budget runs out around ${DateFormat.MMMd().format(exhaustionDate)} '
              '(in $daysLeft day${daysLeft == 1 ? '' : 's'}).'
          : 'At this pace, the budget comfortably covers the rest of the month.';
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Text(
                  '${summary.clarityScore.riskLevel.name[0].toUpperCase()}${summary.clarityScore.riskLevel.name.substring(1)} cash-flow risk',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700, color: color),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(outlook, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _MiniStat(label: 'Velocity', value: '${money(velocity)}/day'),
                ),
                Expanded(
                  child: _MiniStat(
                    label: remaining >= 0 ? 'Remaining' : 'Over budget',
                    value: money(remaining.abs()),
                    color: remaining < 0 ? RiskColors.high : null,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;

  const _MiniStat({required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6))),
        const SizedBox(height: 2),
        Text(value, style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700, color: color)),
      ],
    );
  }
}

class _ExpenseHistoryList extends StatelessWidget {
  final List<Expense> expenses;

  const _ExpenseHistoryList({required this.expenses});

  @override
  Widget build(BuildContext context) {
    if (expenses.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Text(
            'No expenses logged yet. Tap + to add your first one.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
          ),
        ),
      );
    }

    return Card(
      child: Column(
        children: List.generate(expenses.length, (i) {
          final expense = expenses[i];
          return Column(
            children: [
              if (i > 0) const Divider(height: 1),
              _ExpenseTile(expense: expense),
            ],
          );
        }),
      ),
    );
  }
}

class _ExpenseTile extends ConsumerWidget {
  final Expense expense;

  const _ExpenseTile({required this.expense});

  IconData get _icon {
    switch (expense.category) {
      case ExpenseCategory.groceries:
        return Icons.local_grocery_store_outlined;
      case ExpenseCategory.cafesAndDining:
        return Icons.local_cafe_outlined;
      case ExpenseCategory.transportation:
        return Icons.directions_transit_outlined;
      case ExpenseCategory.housingAndUtilities:
        return Icons.home_outlined;
      case ExpenseCategory.education:
        return Icons.school_outlined;
      case ExpenseCategory.apparel:
        return Icons.checkroom_outlined;
      case ExpenseCategory.electronics:
        return Icons.devices_outlined;
      case ExpenseCategory.other:
        return Icons.receipt_long_outlined;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final subtitleParts = [
      expense.category.displayName,
      if (expense.storeName != null) expense.storeName!,
      DateFormat.MMMd().format(expense.occurredOn),
    ];
    if (expense.originalCurrency != null) {
      subtitleParts.add('paid in ${expense.originalCurrency}');
    }

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: ZenColors.matchaLight,
        foregroundColor: ZenColors.matchaDark,
        child: Icon(_icon, size: 20),
      ),
      title: Text(expense.title, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(subtitleParts.join(' · ')),
      trailing: Text(
        formatKrwForDisplay(ref, expense.totalEconomicCostKrw),
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700),
      ),
    );
  }
}
