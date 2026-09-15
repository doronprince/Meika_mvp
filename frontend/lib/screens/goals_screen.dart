import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/network/api_error.dart';
import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/dashboard_summary.dart';
import '../data/models/goal.dart';
import '../data/repositories/goal_repository.dart';
import '../providers/currency_providers.dart';
import '../providers/goal_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';
import 'add_goal_screen.dart';

final _dateFormat = DateFormat.yMMMd();

Color verdictColor(GoalVerdict verdict) {
  switch (verdict) {
    case GoalVerdict.onTrack:
    case GoalVerdict.achieved:
      return RiskColors.low;
    case GoalVerdict.atRisk:
      return RiskColors.moderate;
    case GoalVerdict.offTrack:
    case GoalVerdict.missed:
      return RiskColors.high;
    case GoalVerdict.insufficientData:
      return ZenColors.sumi.withValues(alpha: 0.5);
  }
}

/// The currency amounts are typed in: the preferred display currency when a
/// live rate is loaded, otherwise KRW. [rateFromKrw] converts KRW -> currency,
/// so a typed amount becomes KRW by dividing by it.
({String code, double rateFromKrw}) entryCurrency(WidgetRef ref) {
  final code = ref.watch(preferredCurrencyProvider);
  if (code == 'KRW') return (code: 'KRW', rateFromKrw: 1.0);
  final rate = ref.watch(fxRatesProvider).valueOrNull?[code];
  return rate == null ? (code: 'KRW', rateFromKrw: 1.0) : (code: code, rateFromKrw: rate);
}

class GoalsScreen extends ConsumerWidget {
  const GoalsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final goals = ref.watch(goalListProvider);

    return Scaffold(
      backgroundColor: ZenColors.washi,
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: ZenColors.matcha,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add_rounded),
        label: const Text('New goal'),
        onPressed: () async {
          final saved = await Navigator.of(context).push<bool>(
            MaterialPageRoute(builder: (_) => const AddGoalScreen()),
          );
          if (saved == true) ref.invalidate(goalListProvider);
        },
      ),
      body: RefreshIndicator(
        color: ZenColors.matcha,
        onRefresh: () => ref.refresh(goalListProvider.future),
        child: AsyncValueView<List<Goal>>(
          value: goals,
          onRetry: () => ref.invalidate(goalListProvider),
          builder: (context, data) => BoundedContent(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
              children: data.isEmpty
                  ? const [_EmptyGoals()]
                  : [
                      for (final goal in data)
                        Padding(padding: const EdgeInsets.only(bottom: 16), child: _GoalCard(goal: goal)),
                    ],
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptyGoals extends StatelessWidget {
  const _EmptyGoals();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Icon(Icons.flag_outlined, size: 40, color: ZenColors.sumi.withValues(alpha: 0.4)),
            const SizedBox(height: 12),
            Text('No goals yet', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(
              'Set a savings target or cap a spending category. Meika forecasts whether your real pace gets you '
              'there — and shows the math behind every verdict.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65)),
            ),
          ],
        ),
      ),
    );
  }
}

class _GoalCard extends ConsumerWidget {
  final Goal goal;

  const _GoalCard({required this.goal});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final f = goal.forecast;
    final color = verdictColor(f.verdict);
    final isSavings = goal.goalType == GoalType.savings;
    String money(num v) => formatKrwForDisplay(ref, v);
    final subtitle = isSavings
        ? 'Savings goal · by ${_dateFormat.format(goal.targetDate)}'
        : 'Spending cap · ${goal.category?.displayName ?? 'All spending'} · by ${_dateFormat.format(goal.targetDate)}';
    final canContribute = isSavings && f.verdict != GoalVerdict.achieved && f.verdict != GoalVerdict.missed;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 8, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 8),
                      Text(goal.name, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.55)),
                      ),
                    ],
                  ),
                ),
                _VerdictChip(verdict: f.verdict, color: color),
                PopupMenuButton<String>(
                  icon: Icon(Icons.more_vert_rounded, color: ZenColors.sumi.withValues(alpha: 0.5)),
                  onSelected: (_) => _confirmDelete(context, ref),
                  itemBuilder: (_) => const [PopupMenuItem(value: 'delete', child: Text('Delete goal'))],
                ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(money(f.progressKrw),
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                      Text('of ${money(goal.targetAmountKrw)}',
                          style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6))),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: (f.progressPercent / 100).clamp(0.0, 1.0),
                      minHeight: 10,
                      backgroundColor: ZenColors.matchaLight,
                      valueColor: AlwaysStoppedAnimation(color),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Day ${f.daysElapsed} of ${f.daysTotal} · ${f.daysRemaining} day(s) left',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.5)),
                  ),
                  const SizedBox(height: 12),
                  if (f.daysElapsed > 0)
                    _StatLine(label: isSavings ? 'Saving pace' : 'Spending pace', value: '${money(f.paceKrwPerDay)} / day'),
                  if (f.projectedFinalKrw != null) ...[
                    const SizedBox(height: 6),
                    _StatLine(label: 'Projected finish', value: money(f.projectedFinalKrw!), valueColor: color),
                  ],
                  if (f.requiredKrwPerDay != null) ...[
                    const SizedBox(height: 6),
                    _StatLine(
                      label: isSavings ? 'Needed to hit target' : 'Daily allowance left',
                      value: '${money(f.requiredKrwPerDay!)} / day',
                    ),
                  ],
                  const SizedBox(height: 12),
                  const Divider(height: 1),
                  const SizedBox(height: 12),
                  ...f.factors.map((factor) => _FactorRow(factor: factor)),
                  if (canContribute)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton.icon(
                        icon: const Icon(Icons.add_rounded, size: 18),
                        label: const Text('Log contribution'),
                        onPressed: () => _logContribution(context, ref),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _logContribution(BuildContext context, WidgetRef ref) async {
    final currency = entryCurrency(ref);
    final amount = await showDialog<double>(
      context: context,
      builder: (_) => _ContributionDialog(currencyCode: currency.code),
    );
    if (amount == null) return;
    try {
      await ref.read(goalRepositoryProvider).addContribution(goal.id, amount / currency.rateFromKrw);
      ref.invalidate(goalListProvider);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
      }
    }
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Delete goal?'),
        content: Text('"${goal.name}" and its contribution history will be removed.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(goalRepositoryProvider).deleteGoal(goal.id);
      ref.invalidate(goalListProvider);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
      }
    }
  }
}

class _ContributionDialog extends StatefulWidget {
  final String currencyCode;

  const _ContributionDialog({required this.currencyCode});

  @override
  State<_ContributionDialog> createState() => _ContributionDialogState();
}

class _ContributionDialogState extends State<_ContributionDialog> {
  final _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final value = double.tryParse(_controller.text.trim());
    if (value == null || value == 0) {
      setState(() => _error = 'Enter a non-zero amount');
      return;
    }
    Navigator.of(context).pop(value);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Log contribution'),
      content: TextField(
        controller: _controller,
        autofocus: true,
        keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^-?\d*\.?\d{0,2}'))],
        decoration: InputDecoration(
          labelText: 'Amount (${widget.currencyCode})',
          helperText: 'Use a negative amount for a withdrawal',
          errorText: _error,
        ),
        onSubmitted: (_) => _submit(),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancel')),
        TextButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }
}

class _VerdictChip extends StatelessWidget {
  final GoalVerdict verdict;
  final Color color;

  const _VerdictChip({required this.verdict, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
      child: Text(
        verdict.label,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(color: color, fontWeight: FontWeight.w700),
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
        Text(value, style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700, color: valueColor)),
      ],
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
