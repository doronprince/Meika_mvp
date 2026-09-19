import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/exposure.dart';
import '../data/repositories/exposure_repository.dart';
import '../providers/currency_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';

final _shortDate = DateFormat('EEE d MMM');

TextStyle? _muted(BuildContext context) =>
    Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65));

TextStyle? _title(BuildContext context) =>
    Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700);

const _quickPlatforms = [
  ('Instagram', ExposureKind.socialFeed),
  ('TikTok', ExposureKind.socialFeed),
  ('YouTube', ExposureKind.influencerContent),
  ('Coupang', ExposureKind.shoppingApp),
  ('Naver Shopping', ExposureKind.shoppingApp),
];

class ExposureScreen extends ConsumerWidget {
  const ExposureScreen({super.key});

  void _refresh(WidgetRef ref) {
    ref.invalidate(exposureSessionsProvider);
    ref.invalidate(exposureInsightsProvider);
  }

  Future<void> _log(BuildContext context, WidgetRef ref) async {
    final platformController = TextEditingController();
    var kind = ExposureKind.socialFeed;
    var minutes = 30.0;
    var day = DateTime.now();

    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Log screen time'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final (name, k) in _quickPlatforms)
                      ActionChip(
                        label: Text(name),
                        onPressed: () => setDialogState(() {
                          platformController.text = name;
                          kind = k;
                        }),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: platformController,
                  decoration: const InputDecoration(labelText: 'App or site'),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<ExposureKind>(
                  initialValue: kind,
                  key: ValueKey(kind),
                  decoration: const InputDecoration(labelText: 'What kind of content'),
                  items: ExposureKind.values
                      .map((k) => DropdownMenuItem(value: k, child: Text(k.displayName)))
                      .toList(),
                  onChanged: (k) => setDialogState(() => kind = k ?? kind),
                ),
                const SizedBox(height: 12),
                Text('${minutes.round()} minutes'),
                Slider(
                  value: minutes,
                  min: 5,
                  max: 240,
                  divisions: 47,
                  activeColor: ZenColors.matcha,
                  onChanged: (v) => setDialogState(() => minutes = v),
                ),
                Row(
                  children: [
                    Expanded(child: Text(_shortDate.format(day))),
                    TextButton(
                      onPressed: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: day,
                          firstDate: DateTime.now().subtract(const Duration(days: 90)),
                          lastDate: DateTime.now(),
                        );
                        if (picked != null) setDialogState(() => day = picked);
                      },
                      child: const Text('Change day'),
                    ),
                  ],
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
    final platform = platformController.text.trim();
    if (platform.isEmpty) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Name the app or site.')));
      }
      return;
    }
    try {
      await ref.read(exposureRepositoryProvider).logSession(
            occurredOn: day,
            platform: platform,
            kind: kind,
            minutes: minutes.round(),
          );
      _refresh(ref);
    } on Exception catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not save: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final insights = ref.watch(exposureInsightsProvider);
    final sessions = ref.watch(exposureSessionsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Exposure & spending')),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: ZenColors.matcha,
        foregroundColor: Colors.white,
        onPressed: () => _log(context, ref),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Log screen time'),
      ),
      body: RefreshIndicator(
        color: ZenColors.matcha,
        onRefresh: () async => _refresh(ref),
        child: BoundedContent(
          maxWidth: 640,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
            children: [
              Text(
                'Does time on feeds and shopping apps line up with your spending? Meika only sees what you log here; '
                'it has no access to your apps.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.7)),
              ),
              const SizedBox(height: 12),
              AsyncValueView<ExposureInsightReport>(
                value: insights,
                onRetry: () => ref.invalidate(exposureInsightsProvider),
                builder: (context, report) => _Insights(report: report),
              ),
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Recent screen time', style: _title(context)),
                      AsyncValueView<List<ExposureSessionEntry>>(
                        value: sessions,
                        onRetry: () => ref.invalidate(exposureSessionsProvider),
                        builder: (context, items) => items.isEmpty
                            ? Padding(
                                padding: const EdgeInsets.only(top: 6),
                                child: Text('Nothing logged yet.', style: _muted(context)),
                              )
                            : Column(
                                children: [
                                  for (final s in items.take(14))
                                    Row(
                                      children: [
                                        Expanded(
                                          child: Padding(
                                            padding: const EdgeInsets.symmetric(vertical: 6),
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                Text('${s.platform} · ${s.minutes} min',
                                                    style: const TextStyle(fontWeight: FontWeight.w600)),
                                                Text('${s.kind.displayName} · ${_shortDate.format(s.occurredOn)}',
                                                    style: _muted(context)),
                                              ],
                                            ),
                                          ),
                                        ),
                                        IconButton(
                                          tooltip: 'Remove',
                                          icon: const Icon(Icons.delete_outline_rounded, size: 20),
                                          onPressed: () async {
                                            await ref.read(exposureRepositoryProvider).deleteSession(s.id);
                                            _refresh(ref);
                                          },
                                        ),
                                      ],
                                    ),
                                ],
                              ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Insights extends ConsumerWidget {
  final ExposureInsightReport report;

  const _Insights({required this.report});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final nudge = report.intervention;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          color: nudge.triggered ? const Color(0xFFFBF1E3) : null,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  nudge.triggered ? Icons.pan_tool_alt_rounded : Icons.self_improvement_rounded,
                  color: nudge.triggered ? RiskColors.moderate : ZenColors.matchaDark,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(nudge.triggered ? 'Pause before you buy' : 'No nudge today', style: _title(context)),
                      const SizedBox(height: 4),
                      Text(nudge.message),
                      if (nudge.suggestion != null) ...[
                        const SizedBox(height: 6),
                        Text(nudge.suggestion!, style: const TextStyle(fontWeight: FontWeight.w600)),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (!report.computed)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Not enough data yet', style: _title(context)),
                  const SizedBox(height: 8),
                  Text('${report.trackedDays} of 28 tracked days · ${report.daysWithExposure} of 8 days with screen time'),
                  const SizedBox(height: 8),
                  Text(report.factors.last.detail, style: _muted(context)),
                ],
              ),
            ),
          )
        else ...[
          _AssociationCard(report: report),
          if (report.effect != null) ...[
            const SizedBox(height: 12),
            _EffectCard(effect: report.effect!),
          ],
          const SizedBox(height: 12),
          _ExploratoryCard(report: report),
        ],
        const SizedBox(height: 12),
        Card(
          child: Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              title: const Text('Why, and what this can\'t tell you', style: TextStyle(fontWeight: FontWeight.w700)),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              children: [
                for (final f in report.factors)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(f.label, style: const TextStyle(fontWeight: FontWeight.w600)),
                        Text(f.detail, style: _muted(context)),
                      ],
                    ),
                  ),
                const Divider(),
                for (final item in report.limitations)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text('• $item', style: _muted(context)),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _AssociationCard extends StatelessWidget {
  final ExposureInsightReport report;

  const _AssociationCard({required this.report});

  @override
  Widget build(BuildContext context) {
    final p = report.primary!;
    final found = report.associationFound;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(found ? 'Screen time lines up with your spending' : 'No clear link found', style: _title(context)),
            const SizedBox(height: 8),
            Row(
              children: [
                _Stat(label: 'Correlation (ρ)', value: p.spearmanRho == null ? 'n/a' : p.spearmanRho!.toStringAsFixed(2)),
                _Stat(label: 'p-value', value: p.pValue == null ? 'n/a' : p.pValue!.toStringAsFixed(3)),
                _Stat(label: 'Days', value: '${p.nDays}'),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Exposure on a day vs discretionary spending that day and the next, with weekly rhythm removed. '
              '${found ? 'An association, not proof one causes the other.' : 'A link needs p below 0.05.'}',
              style: _muted(context),
            ),
          ],
        ),
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;

  const _Stat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: _muted(context)),
          Text(value, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _EffectCard extends ConsumerWidget {
  final EffectSize effect;

  const _EffectCard({required this.effect});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final maxValue = [effect.meanAfterHighKrw, effect.meanAfterZeroKrw, 1.0].reduce((a, b) => a > b ? a : b);
    Widget bar(String label, double value, Color color) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: Text(label)),
                  Text(formatKrwForDisplay(ref, value), style: const TextStyle(fontWeight: FontWeight.w700)),
                ],
              ),
              const SizedBox(height: 4),
              LinearProgressIndicator(
                value: (value / maxValue).clamp(0.0, 1.0),
                minHeight: 8,
                borderRadius: BorderRadius.circular(4),
                backgroundColor: ZenColors.sandBorder,
                valueColor: AlwaysStoppedAnimation(color),
              ),
            ],
          ),
        );

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Discretionary spending that day and the next', style: _title(context)),
            const SizedBox(height: 12),
            bar('After ${effect.thresholdMinutes}+ min days (${effect.highDays})', effect.meanAfterHighKrw, RiskColors.moderate),
            bar('After days with none (${effect.zeroDays})', effect.meanAfterZeroKrw, ZenColors.matcha),
          ],
        ),
      ),
    );
  }
}

class _ExploratoryCard extends StatelessWidget {
  final ExposureInsightReport report;

  const _ExploratoryCard({required this.report});

  String _fmt(double? v) => v == null ? 'n/a' : v.toStringAsFixed(2);

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Exploratory breakdown', style: _title(context)),
            const SizedBox(height: 4),
            Text('Not corrected for multiple comparisons; read as hints.', style: _muted(context)),
            const SizedBox(height: 8),
            for (final (lag, stats) in report.lags)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Expanded(child: Text(lag == 0 ? 'Same day' : '$lag day${lag == 1 ? '' : 's'} later')),
                    Text('ρ ${_fmt(stats.spearmanRho)} · p ${stats.pValue == null ? 'n/a' : stats.pValue!.toStringAsFixed(3)}'),
                  ],
                ),
              ),
            if (report.byKind.isNotEmpty) const Divider(height: 20),
            for (final (kind, minutes, stats) in report.byKind)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    Expanded(child: Text('${kind.displayName} ($minutes min)')),
                    Text('ρ ${_fmt(stats.spearmanRho)}'),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
