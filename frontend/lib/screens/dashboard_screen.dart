import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/format/currency.dart';
import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/dashboard_summary.dart';
import '../providers/dashboard_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(dashboardSummaryProvider);

    return RefreshIndicator(
      color: ZenColors.matcha,
      onRefresh: () => ref.refresh(dashboardSummaryProvider.future),
      child: AsyncValueView<DashboardSummary>(
        value: summary,
        onRetry: () => ref.invalidate(dashboardSummaryProvider),
        builder: (context, data) => BoundedContent(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
            children: [
              _ClarityScoreCard(score: data.clarityScore),
              const SizedBox(height: 16),
              _BudgetSnapshotCard(summary: data),
              const SizedBox(height: 16),
              _VelocityCard(summary: data),
              const SizedBox(height: 16),
              _CategoryBreakdownCard(items: data.categoryBreakdown),
            ],
          ),
        ),
      ),
    );
  }
}

class _ClarityScoreCard extends StatelessWidget {
  final ClarityScore score;

  const _ClarityScoreCard({required this.score});

  @override
  Widget build(BuildContext context) {
    final color = RiskColors.forLevel(score.riskLevel);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                SizedBox(
                  width: 72,
                  height: 72,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      CircularProgressIndicator(
                        value: score.value / 100,
                        strokeWidth: 6,
                        backgroundColor: ZenColors.sandBorder,
                        valueColor: AlwaysStoppedAnimation(color),
                      ),
                      Text(
                        '${score.value}',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Financial Clarity Score',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${score.riskLevel.name[0].toUpperCase()}${score.riskLevel.name.substring(1)} risk',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: color, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 12),
            ...score.factors.map((f) => _FactorRow(factor: f)),
          ],
        ),
      ),
    );
  }
}

class _FactorRow extends StatelessWidget {
  final ClarityFactor factor;

  const _FactorRow({required this.factor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(factor.label, style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 2),
          Text(
            factor.detail,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65)),
          ),
        ],
      ),
    );
  }
}

class _BudgetSnapshotCard extends StatelessWidget {
  final DashboardSummary summary;

  const _BudgetSnapshotCard({required this.summary});

  @override
  Widget build(BuildContext context) {
    final ratio = summary.monthlyBudgetKrw > 0
        ? (summary.totalSpentThisMonthKrw / summary.monthlyBudgetKrw).clamp(0.0, 1.0)
        : 0.0;
    final overBudget = summary.remainingBudgetKrw < 0;
    final barColor = overBudget ? RiskColors.high : (ratio > 0.85 ? RiskColors.moderate : RiskColors.low);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('This Month', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(formatKrw(summary.totalSpentThisMonthKrw),
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                Text('of ${formatKrw(summary.monthlyBudgetKrw)}',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6))),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: ratio,
                minHeight: 10,
                backgroundColor: ZenColors.matchaLight,
                valueColor: AlwaysStoppedAnimation(barColor),
              ),
            ),
            const SizedBox(height: 10),
            Text(
              overBudget
                  ? '${formatKrw(-summary.remainingBudgetKrw)} over budget'
                  : '${formatKrw(summary.remainingBudgetKrw)} remaining',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: barColor, fontWeight: FontWeight.w600),
            ),
            Text(
              'Day ${summary.daysElapsedThisMonth} of ${summary.daysInMonth}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.5)),
            ),
          ],
        ),
      ),
    );
  }
}

class _VelocityCard extends StatelessWidget {
  final DashboardSummary summary;

  const _VelocityCard({required this.summary});

  @override
  Widget build(BuildContext context) {
    final projected = summary.projectedMonthEndSpendKrw;
    final overage = summary.projectedOverageKrw ?? 0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Predictive Budgeting', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            _StatLine(
              label: 'Spending velocity',
              value: '${formatKrw(summary.spendingVelocityKrwPerDay)} / day',
            ),
            const SizedBox(height: 8),
            if (projected == null)
              Text(
                'Projection needs a few more days of data this month.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
              )
            else ...[
              _StatLine(label: 'Projected month-end spend', value: formatKrw(projected)),
              if (overage > 0) ...[
                const SizedBox(height: 8),
                _StatLine(
                  label: 'Projected overage',
                  value: formatKrw(overage),
                  valueColor: RiskColors.high,
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _StatLine extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;

  const _StatLine({required this.label, required this.value, this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.7))),
        Text(
          value,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700, color: valueColor),
        ),
      ],
    );
  }
}

class _CategoryBreakdownCard extends StatelessWidget {
  final List<CategoryBreakdownItem> items;

  const _CategoryBreakdownCard({required this.items});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Category Breakdown', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            if (items.isEmpty)
              Text(
                'No expenses logged yet this month.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
              )
            else
              ...items.map((item) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(item.category.displayName, style: Theme.of(context).textTheme.bodyMedium),
                            Text(
                              formatKrw(item.totalKrw),
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: LinearProgressIndicator(
                            value: (item.percentOfSpend / 100).clamp(0.0, 1.0),
                            minHeight: 6,
                            backgroundColor: ZenColors.matchaLight,
                            valueColor: const AlwaysStoppedAnimation(ZenColors.matcha),
                          ),
                        ),
                      ],
                    ),
                  )),
          ],
        ),
      ),
    );
  }
}
