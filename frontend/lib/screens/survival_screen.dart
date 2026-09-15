import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/format/currency.dart';
import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/dashboard_summary.dart';
import '../data/models/expense_category.dart';
import '../data/models/income_stream.dart';
import '../data/models/survival_report.dart';
import '../data/models/user_profile.dart';
import '../data/repositories/survival_repository.dart';
import '../providers/currency_providers.dart';
import '../providers/survival_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';
import '../widgets/runway_chart.dart';

const _horizonMonths = 60;

class SurvivalScreen extends ConsumerStatefulWidget {
  const SurvivalScreen({super.key});

  @override
  ConsumerState<SurvivalScreen> createState() => _SurvivalScreenState();
}

class _SurvivalScreenState extends ConsumerState<SurvivalScreen> {
  /// Preset key -> the shock as it will be sent, magnitude possibly edited.
  /// Insertion order is the order shocks are sent in.
  final Map<String, Map<String, dynamic>> _selected = {};
  double _cutPct = 50;

  String get _requestJson => jsonEncode({
        'shocks': _selected.values.toList(),
        'horizon_months': _horizonMonths,
        'discretionary_cut_pct': _cutPct.round(),
      });

  void _refreshAll({bool clearShocks = false}) {
    if (clearShocks) setState(_selected.clear);
    ref.invalidate(userProfileProvider);
    ref.invalidate(incomeStreamsProvider);
    ref.invalidate(shockPresetsProvider);
    ref.invalidate(survivalReportProvider);
  }

  @override
  Widget build(BuildContext context) {
    final report = ref.watch(survivalReportProvider(_requestJson));

    return Scaffold(
      appBar: AppBar(title: const Text('Survival runway')),
      body: RefreshIndicator(
        color: ZenColors.matcha,
        onRefresh: () async => _refreshAll(),
        child: BoundedContent(
          maxWidth: 640,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            children: [
              Text(
                'How long would your savings last if several things went wrong at once, and which of them does the damage?',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.7)),
              ),
              const SizedBox(height: 16),
              _SavingsCard(profile: ref.watch(userProfileProvider), onChanged: _refreshAll),
              const SizedBox(height: 12),
              _IncomeCard(streams: ref.watch(incomeStreamsProvider), onChanged: () => _refreshAll(clearShocks: true)),
              const SizedBox(height: 12),
              _ShocksCard(
                presets: ref.watch(shockPresetsProvider),
                selected: _selected,
                cutPct: _cutPct,
                onToggle: (preset, on) => setState(() {
                  if (on) {
                    _selected[preset.key] = Map<String, dynamic>.from(preset.shock);
                  } else {
                    _selected.remove(preset.key);
                  }
                }),
                onEdited: (key, shock) => setState(() => _selected[key] = shock),
                onCutChanged: (value) => setState(() => _cutPct = value),
              ),
              const SizedBox(height: 12),
              AsyncValueView<SurvivalReport>(
                value: report,
                onRetry: () => ref.invalidate(survivalReportProvider),
                builder: (context, data) => _ReportSection(report: data, hasShocks: _selected.isNotEmpty),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

void _showError(BuildContext context, Object error) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Something went wrong: $error')));
}

class _CardTitle extends StatelessWidget {
  final String title;
  final Widget? trailing;

  const _CardTitle(this.title, {this.trailing});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

TextStyle? _muted(BuildContext context) =>
    Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65));

class _SavingsCard extends ConsumerWidget {
  final AsyncValue<UserProfile> profile;
  final VoidCallback onChanged;

  const _SavingsCard({required this.profile, required this.onChanged});

  Future<void> _edit(BuildContext context, WidgetRef ref, double? currentKrw) async {
    final currency = ref.read(preferredCurrencyProvider);
    final rate = currency == 'KRW' ? 1.0 : ref.read(fxRatesProvider).valueOrNull?[currency];
    // Enter the figure in the display currency when a live rate exists;
    // otherwise fall back to KRW rather than guess a conversion.
    final inputCurrency = rate == null ? 'KRW' : currency;
    final effectiveRate = rate ?? 1.0;
    final controller = TextEditingController(
      text: currentKrw == null ? '' : (currentKrw * effectiveRate).toStringAsFixed(inputCurrency == 'KRW' ? 0 : 2),
    );

    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Liquid savings'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Cash and accounts you can withdraw from right away.', style: _muted(context)),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              autofocus: true,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(labelText: 'Amount ($inputCurrency)'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, ''), child: const Text('Clear')),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Save')),
        ],
      ),
    );
    if (result == null) return;

    double? krw;
    if (result.trim().isNotEmpty) {
      final parsed = double.tryParse(result.replaceAll(',', '').trim());
      if (parsed == null || parsed < 0) return;
      krw = parsed / effectiveRate;
    }
    try {
      await ref.read(survivalRepositoryProvider).setLiquidSavings(krw);
      onChanged();
    } on Exception catch (e) {
      if (context.mounted) _showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final savings = profile.valueOrNull?.liquidSavingsKrw;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Liquid savings', style: _muted(context)),
                  const SizedBox(height: 4),
                  Text(
                    savings == null ? 'Not set' : formatKrwForDisplay(ref, savings),
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
                  ),
                ],
              ),
            ),
            TextButton(
              onPressed: profile.hasValue ? () => _edit(context, ref, savings) : null,
              child: Text(savings == null ? 'Add' : 'Edit'),
            ),
          ],
        ),
      ),
    );
  }
}

class _IncomeCard extends ConsumerWidget {
  final AsyncValue<List<IncomeStream>> streams;
  final VoidCallback onChanged;

  const _IncomeCard({required this.streams, required this.onChanged});

  Future<void> _add(BuildContext context, WidgetRef ref) async {
    final labelController = TextEditingController();
    final amountController = TextEditingController();
    var kind = IncomeKind.partTime;
    var currency = ref.read(preferredCurrencyProvider);
    final currencies = supportedCurrencies.toList()..sort();

    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Add monthly income'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: labelController,
                  decoration: const InputDecoration(labelText: 'Label (e.g. Cafe shifts)'),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<IncomeKind>(
                  initialValue: kind,
                  decoration: const InputDecoration(labelText: 'Kind'),
                  items: IncomeKind.values
                      .map((k) => DropdownMenuItem(value: k, child: Text(k.displayName)))
                      .toList(),
                  onChanged: (k) => setDialogState(() => kind = k ?? kind),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: amountController,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: const InputDecoration(labelText: 'Amount per month'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    DropdownButton<String>(
                      value: currency,
                      items: currencies.map((c) => DropdownMenuItem(value: c, child: Text(c))).toList(),
                      onChanged: (c) => setDialogState(() => currency = c ?? currency),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  'Pick the currency it is actually paid in. An allowance from home stays in that currency, so a '
                  'devaluation shock can reach it.',
                  style: _muted(context),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save')),
          ],
        ),
      ),
    );
    if (saved != true) return;

    final amount = double.tryParse(amountController.text.replaceAll(',', '').trim());
    final label = labelController.text.trim();
    if (amount == null || amount <= 0 || label.isEmpty) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter a label and a positive amount.')));
      }
      return;
    }
    try {
      await ref.read(survivalRepositoryProvider).createIncomeStream(
            label: label,
            kind: kind,
            monthlyAmount: amount,
            currency: currency,
          );
      onChanged();
    } on Exception catch (e) {
      if (context.mounted) _showError(context, e);
    }
  }

  Future<void> _delete(BuildContext context, WidgetRef ref, IncomeStream stream) async {
    try {
      await ref.read(survivalRepositoryProvider).deleteIncomeStream(stream.id);
      onChanged();
    } on Exception catch (e) {
      if (context.mounted) _showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _CardTitle(
              'Monthly income',
              trailing: TextButton.icon(
                onPressed: () => _add(context, ref),
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('Add'),
              ),
            ),
            AsyncValueView<List<IncomeStream>>(
              value: streams,
              onRetry: () => ref.invalidate(incomeStreamsProvider),
              builder: (context, items) {
                if (items.isEmpty) {
                  return Padding(
                    padding: const EdgeInsets.only(top: 4, right: 8),
                    child: Text('No income added yet, so the runway assumes zero income.', style: _muted(context)),
                  );
                }
                return Column(
                  children: [
                    for (final stream in items)
                      Row(
                        children: [
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(vertical: 6),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(stream.label, style: const TextStyle(fontWeight: FontWeight.w600)),
                                  Text(
                                    '${stream.kind.displayName} · ${formatCurrency(stream.monthlyAmount, stream.currency)}'
                                    '${stream.currency == 'KRW' ? '' : ' ≈ ${formatKrwForDisplay(ref, stream.monthlyAmountKrwSnapshot)}'}'
                                    '${stream.isActive ? '' : ' · paused'}',
                                    style: _muted(context),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          IconButton(
                            tooltip: 'Remove',
                            icon: const Icon(Icons.delete_outline_rounded, size: 20),
                            onPressed: () => _delete(context, ref, stream),
                          ),
                        ],
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _ShocksCard extends StatelessWidget {
  final AsyncValue<List<ShockPreset>> presets;
  final Map<String, Map<String, dynamic>> selected;
  final double cutPct;
  final void Function(ShockPreset preset, bool on) onToggle;
  final void Function(String key, Map<String, dynamic> shock) onEdited;
  final ValueChanged<double> onCutChanged;

  const _ShocksCard({
    required this.presets,
    required this.selected,
    required this.cutPct,
    required this.onToggle,
    required this.onEdited,
    required this.onCutChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _CardTitle('Shocks to test together'),
            const SizedBox(height: 4),
            Text('Suggested from your own income and spending. Pick any combination.', style: _muted(context)),
            const SizedBox(height: 12),
            AsyncValueView<List<ShockPreset>>(
              value: presets,
              builder: (context, items) => Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final preset in items)
                        Tooltip(
                          message: preset.description,
                          child: FilterChip(
                            label: Text(preset.title),
                            selected: selected.containsKey(preset.key),
                            selectedColor: ZenColors.matchaLight,
                            checkmarkColor: ZenColors.matchaDark,
                            onSelected: (on) => onToggle(preset, on),
                          ),
                        ),
                    ],
                  ),
                  for (final preset in items)
                    if (selected.containsKey(preset.key))
                      _ShockMagnitude(
                        key: ValueKey(preset.key),
                        preset: preset,
                        shock: selected[preset.key]!,
                        onChanged: (shock) => onEdited(preset.key, shock),
                      ),
                ],
              ),
            ),
            const Divider(height: 28),
            Text(
              'When savings drop below 3 months of essentials, cut discretionary spending by ${cutPct.round()}%',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            Slider(
              value: cutPct,
              min: 0,
              max: 100,
              divisions: 20,
              activeColor: ZenColors.matcha,
              label: '${cutPct.round()}%',
              onChanged: onCutChanged,
            ),
          ],
        ),
      ),
    );
  }
}

/// A slider for the one number that defines a shock's severity. The request
/// only re-runs when the slider is released, not on every drag frame.
class _ShockMagnitude extends ConsumerStatefulWidget {
  final ShockPreset preset;
  final Map<String, dynamic> shock;
  final ValueChanged<Map<String, dynamic>> onChanged;

  const _ShockMagnitude({super.key, required this.preset, required this.shock, required this.onChanged});

  @override
  ConsumerState<_ShockMagnitude> createState() => _ShockMagnitudeState();
}

class _ShockMagnitudeState extends ConsumerState<_ShockMagnitude> {
  late double _value;

  String get _field => switch (widget.shock['kind']) {
        'one_off_expense' => 'amount_krw',
        'inflation' => 'annual_pct',
        _ => 'pct',
      };

  (double, double, int) get _range {
    switch (widget.shock['kind']) {
      case 'one_off_expense':
        final original = parseAmount(widget.preset.shock['amount_krw']);
        return (original * 0.25, original * 4, 15);
      case 'inflation':
        return (1, 30, 29);
      case 'currency_devaluation':
        return (5, 60, 11);
      default:
        return (5, 100, 19);
    }
  }

  @override
  void initState() {
    super.initState();
    final (min, max, _) = _range;
    _value = parseAmount(widget.shock[_field]).clamp(min, max).toDouble();
  }

  String _display(double value) => switch (widget.shock['kind']) {
        'one_off_expense' => formatKrwForDisplay(ref, value),
        'inflation' => '${value.round()}% a year',
        _ => '${value.round()}%',
      };

  @override
  Widget build(BuildContext context) {
    final (min, max, divisions) = _range;
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${widget.preset.title}: ${_display(_value)}', style: Theme.of(context).textTheme.bodyMedium),
          Slider(
            value: _value,
            min: min,
            max: max,
            divisions: divisions,
            activeColor: RiskColors.high,
            onChanged: (v) => setState(() => _value = v),
            onChangeEnd: (v) {
              final updated = Map<String, dynamic>.from(widget.shock);
              updated[_field] = _field == 'amount_krw' ? double.parse(v.toStringAsFixed(2)) : v.roundToDouble();
              widget.onChanged(updated);
            },
          ),
        ],
      ),
    );
  }
}

String _runwayText(RunwayResult? runway, int horizon) {
  if (runway == null) return '—';
  if (runway.sustainable) return '$horizon+ mo';
  return '${runway.months!.toStringAsFixed(1)} mo';
}

int _visibleMonths(SurvivalReport report) {
  final finite = [report.baselineRunway, report.shockedRunway, report.withCutsRunway]
      .whereType<RunwayResult>()
      .where((r) => !r.sustainable)
      .map((r) => r.months!)
      .toList();
  if (finite.isEmpty) return math.min(report.horizonMonths, 24);
  return (finite.reduce(math.max) * 1.5).ceil().clamp(12, report.horizonMonths).toInt();
}

class _ReportSection extends ConsumerWidget {
  final SurvivalReport report;
  final bool hasShocks;

  const _ReportSection({required this.report, required this.hasShocks});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (report.needsSavings) {
      return Column(
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const _CardTitle('Add your savings to see a runway'),
                  const SizedBox(height: 8),
                  Text(
                    'Meika won\'t guess a starting balance. Your income and spending baseline are ready below.',
                    style: _muted(context),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          _FactorsCard(factors: report.factors),
        ],
      );
    }

    final riskColor = report.riskLevel == null ? ZenColors.sumi : RiskColors.forLevel(report.riskLevel!);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _CardTitle(
                  'Runway',
                  trailing: report.riskLevel == null
                      ? null
                      : Text(
                          '${report.riskLevel!.name[0].toUpperCase()}${report.riskLevel!.name.substring(1)} risk',
                          style: TextStyle(color: riskColor, fontWeight: FontWeight.w700),
                        ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    _RunwayFigure(label: 'No shock', runway: report.baselineRunway, horizon: report.horizonMonths, color: RunwayChart.baselineColor),
                    _RunwayFigure(label: 'With shocks', runway: hasShocks ? report.shockedRunway : null, horizon: report.horizonMonths, color: RunwayChart.shockedColor),
                    _RunwayFigure(label: 'Shocks + cuts', runway: hasShocks ? report.withCutsRunway : null, horizon: report.horizonMonths, color: RunwayChart.withCutsColor),
                  ],
                ),
                if (!hasShocks) ...[
                  const SizedBox(height: 8),
                  Text('Pick shocks above to see how far the runway falls.', style: _muted(context)),
                ],
                const SizedBox(height: 16),
                RunwayChart(
                  startBalanceKrw: report.liquidSavingsKrw ?? 0,
                  points: report.trajectory,
                  visibleMonths: _visibleMonths(report),
                  formatMoney: (v) => formatKrwForDisplay(ref, v),
                ),
              ],
            ),
          ),
        ),
        if (report.attributions.isNotEmpty) ...[
          const SizedBox(height: 12),
          _AttributionCard(report: report),
        ],
        const SizedBox(height: 12),
        _FactorsCard(factors: report.factors),
        const SizedBox(height: 12),
        Card(
          child: Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              title: const Text('Assumptions', style: TextStyle(fontWeight: FontWeight.w700)),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              children: [
                for (final assumption in report.assumptions)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text('• $assumption', style: _muted(context)),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _RunwayFigure extends StatelessWidget {
  final String label;
  final RunwayResult? runway;
  final int horizon;
  final Color color;

  const _RunwayFigure({required this.label, required this.runway, required this.horizon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: _muted(context)),
          const SizedBox(height: 2),
          Text(
            _runwayText(runway, horizon),
            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800, color: color),
          ),
          if (runway?.days != null) Text('≈ ${runway!.days} days', style: _muted(context)),
        ],
      ),
    );
  }
}

class _AttributionCard extends StatelessWidget {
  final SurvivalReport report;

  const _AttributionCard({required this.report});

  @override
  Widget build(BuildContext context) {
    final maxLost = report.attributions.map((a) => a.monthsLost).fold<double>(0, math.max);
    final interaction = report.interactionMonths;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _CardTitle('Which shock does the damage'),
            const SizedBox(height: 4),
            Text(
              'Months of runway each shock takes, averaged over every order the shocks could arrive in.',
              style: _muted(context),
            ),
            const SizedBox(height: 12),
            for (final a in report.attributions)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(a.label, style: const TextStyle(fontWeight: FontWeight.w600))),
                        Text(
                          '−${a.monthsLost.toStringAsFixed(1)} mo${a.sharePct == null ? '' : ' · ${a.sharePct!.round()}%'}',
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    LinearProgressIndicator(
                      value: maxLost > 0 ? (a.monthsLost / maxLost).clamp(0.0, 1.0) : 0,
                      minHeight: 6,
                      borderRadius: BorderRadius.circular(3),
                      backgroundColor: ZenColors.sandBorder,
                      valueColor: const AlwaysStoppedAnimation(RiskColors.high),
                    ),
                    const SizedBox(height: 2),
                    Text('On its own: −${a.standaloneMonthsLost.toStringAsFixed(1)} mo', style: _muted(context)),
                  ],
                ),
              ),
            if (interaction != null && report.attributions.length >= 2)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: ZenColors.matchaLight,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  interaction > 0.05
                      ? 'Compound effect: together these shocks cost ${interaction.toStringAsFixed(1)} months more than '
                          'the sum of each one alone.'
                      : interaction < -0.05
                          ? 'Overlap: together they cost ${(-interaction).toStringAsFixed(1)} months less than the sum '
                              'of each alone, because part of their damage lands on the same money.'
                          : 'These shocks act roughly independently of each other.',
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _FactorsCard extends StatelessWidget {
  final List<ClarityFactor> factors;

  const _FactorsCard({required this.factors});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _CardTitle('Why these numbers'),
            const SizedBox(height: 12),
            for (final factor in factors)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(factor.label, style: const TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 2),
                    Text(factor.detail, style: _muted(context)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
