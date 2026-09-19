import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/claim_report.dart';
import '../data/repositories/claim_repository.dart';
import '../providers/currency_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';

TextStyle? _muted(BuildContext context) =>
    Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65));

TextStyle? _title(BuildContext context) =>
    Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700);

const _examples = [
  'This savings account is guaranteed and risk-free',
  'Bitcoin will double by the end of the year',
  'Toss Bank pays 3.5% interest on deposits',
];

const _stanceText = {
  'sources_lean_supporting': 'Sources mostly use language that backs it',
  'sources_lean_disputing': 'Sources mostly use language that pushes back',
  'sources_disagree': 'Sources are split',
  'no_directional_language': 'No source took a clear side',
  'not_applicable': 'No sources to weigh',
};

const _statusText = {
  'live': 'Live web search',
  'cached': 'Recent search (cached)',
  'live_empty': 'Live search found nothing',
  'quota_exhausted': 'Daily search limit reached',
  'unavailable': 'Search unavailable',
};

class ClaimCheckScreen extends ConsumerStatefulWidget {
  /// Shows this report on open; used by tests and deep links.
  final ClaimReport? initialReport;

  const ClaimCheckScreen({super.key, this.initialReport});

  @override
  ConsumerState<ClaimCheckScreen> createState() => _ClaimCheckScreenState();
}

class _ClaimCheckScreenState extends ConsumerState<ClaimCheckScreen> {
  final _claimController = TextEditingController();
  final _stakeController = TextEditingController();
  ClaimReport? _report;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _report = widget.initialReport;
  }

  @override
  void dispose() {
    _claimController.dispose();
    _stakeController.dispose();
    super.dispose();
  }

  Future<void> _run(Future<ClaimReport> Function() request) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final report = await request();
      setState(() => _report = report);
      ref.invalidate(claimHistoryProvider);
    } on Exception catch (e) {
      setState(() => _error = 'Could not check this claim. $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _submit() {
    final text = _claimController.text.trim();
    if (text.length < 10) {
      setState(() => _error = 'Write out the claim (at least 10 characters).');
      return;
    }
    final stake = double.tryParse(_stakeController.text.replaceAll(',', '').trim());
    final currency = ref.read(preferredCurrencyProvider);
    _run(() => ref.read(claimRepositoryProvider).evaluate(
          text,
          stakeAmount: stake != null && stake > 0 ? stake : null,
          stakeCurrency: stake != null && stake > 0 ? currency : null,
        ));
  }

  @override
  Widget build(BuildContext context) {
    final currency = ref.watch(preferredCurrencyProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Claim check')),
      body: BoundedContent(
        maxWidth: 640,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            Text(
              'Saw a money claim online? Meika weighs where its support comes from and what acting on it would mean '
              'for your budget. It does not fact-check.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.7)),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _claimController,
                      minLines: 2,
                      maxLines: 4,
                      maxLength: 500,
                      decoration: const InputDecoration(labelText: 'The claim, as you saw it'),
                    ),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final example in _examples)
                          ActionChip(
                            label: Text(example, overflow: TextOverflow.ellipsis),
                            onPressed: () => setState(() => _claimController.text = example),
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _stakeController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(labelText: 'How much would you put in? ($currency, optional)'),
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton(
                      onPressed: _busy ? null : _submit,
                      child: _busy
                          ? const SizedBox(
                              width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Text('Check this claim'),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 8),
                      Text(_error!, style: const TextStyle(color: RiskColors.high)),
                    ],
                  ],
                ),
              ),
            ),
            if (_report != null) ...[
              const SizedBox(height: 12),
              _ReportView(report: _report!),
            ],
            const SizedBox(height: 12),
            _History(onOpen: (id) => _run(() => ref.read(claimRepositoryProvider).fetch(id))),
          ],
        ),
      ),
    );
  }
}

class _ReportView extends ConsumerWidget {
  final ClaimReport report;

  const _ReportView({required this.report});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = report.riskLevel == null ? ZenColors.sumi : RiskColors.forLevel(report.riskLevel!);
    final score = report.cautionScore;
    final banded = score != null && report.cautionScoreUpper != null && report.cautionScoreUpper != score;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('"${report.claimText}"', style: const TextStyle(fontStyle: FontStyle.italic)),
                const SizedBox(height: 12),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      score == null ? 'No score' : '$score',
                      style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w800, color: color),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text(
                          score == null
                              ? 'No sources, so no caution score'
                              : banded
                                  ? 'caution, up to ${report.cautionScoreUpper} once you add an amount'
                                  : 'caution out of 100',
                          style: TextStyle(color: color, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(report.disclaimer, style: _muted(context)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('What goes into it', style: _title(context)),
                const SizedBox(height: 12),
                for (final c in report.components)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(child: Text(c.name, style: const TextStyle(fontWeight: FontWeight.w600))),
                            Text(c.computable ? '${c.points!.toStringAsFixed(1)} / ${c.cap}' : '— / ${c.cap}', style: _muted(context)),
                          ],
                        ),
                        const SizedBox(height: 4),
                        LinearProgressIndicator(
                          value: c.computable ? (c.points! / c.cap).clamp(0.0, 1.0) : 0,
                          minHeight: 6,
                          borderRadius: BorderRadius.circular(3),
                          backgroundColor: ZenColors.sandBorder,
                          valueColor: const AlwaysStoppedAnimation(RiskColors.moderate),
                        ),
                        const SizedBox(height: 4),
                        Text(c.detail, style: _muted(context)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        _SourcesCard(report: report),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Your cushion', style: _title(context)),
                const SizedBox(height: 8),
                _Line('Budget headroom this month', formatKrwForDisplay(ref, report.personal.budgetHeadroomKrw)),
                _Line('This month\'s budget lasts',
                    report.personal.budgetRunwayDays == null ? '—' : '${report.personal.budgetRunwayDays!.round()} days'),
                _Line('Savings would last',
                    report.personal.survivalRunwayDays == null ? '—' : '${report.personal.survivalRunwayDays!.round()} days'),
                if (report.stakeAmountKrw != null)
                  _Line('Your amount', formatKrwForDisplay(ref, report.stakeAmountKrw!)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              title: const Text('Why, step by step', style: TextStyle(fontWeight: FontWeight.w700)),
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

class _Line extends StatelessWidget {
  final String label;
  final String value;

  const _Line(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}

class _SourcesCard extends StatelessWidget {
  final ClaimReport report;

  const _SourcesCard({required this.report});

  @override
  Widget build(BuildContext context) {
    final age = report.evidenceAgeDays;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Sources', style: _title(context)),
            const SizedBox(height: 4),
            Text(
              '${_statusText[report.evidenceStatus] ?? report.evidenceStatus}'
              '${age != null && age > 0 ? ' · $age day(s) old' : ''} · '
              '${_stanceText[report.evidenceStance] ?? report.evidenceStance}',
              style: _muted(context),
            ),
            if (report.sources.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('No sources were retrieved for this claim.', style: _muted(context)),
              ),
            for (final s in report.sources)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: InkWell(
                  onTap: () => launchUrl(Uri.parse(s.link), mode: LaunchMode.externalApplication),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(s.title, style: const TextStyle(fontWeight: FontWeight.w600), maxLines: 2, overflow: TextOverflow.ellipsis),
                      Text(
                        '${s.domain} · ${s.tier.replaceAll('_', ' ')} · credibility ${s.credibility} · independence ${s.independence}',
                        style: _muted(context),
                      ),
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          _Tag(s.relevant ? s.stance : 'off topic',
                              s.stance == 'disputes' ? RiskColors.high : s.stance == 'supports' ? ZenColors.matchaDark : ZenColors.sumi),
                          if (s.echoOf != null) _Tag('echo of #${s.echoOf}', ZenColors.sumi),
                          for (final signal in s.conflictSignals) _Tag(signal.label, RiskColors.moderate),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  final String text;
  final Color color;

  const _Tag(this.text, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(text, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
    );
  }
}

class _History extends ConsumerWidget {
  final void Function(String id) onOpen;

  const _History({required this.onOpen});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Earlier checks', style: _title(context)),
            AsyncValueView<List<ClaimSummary>>(
              value: ref.watch(claimHistoryProvider),
              onRetry: () => ref.invalidate(claimHistoryProvider),
              builder: (context, items) => items.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text('None yet.', style: _muted(context)),
                    )
                  : Column(
                      children: [
                        for (final item in items)
                          ListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(item.claimText, maxLines: 2, overflow: TextOverflow.ellipsis),
                            trailing: Text(
                              item.cautionScore == null
                                  ? '—'
                                  : item.cautionScoreUpper != item.cautionScore
                                      ? '${item.cautionScore}-${item.cautionScoreUpper}'
                                      : '${item.cautionScore}',
                              style: TextStyle(
                                fontWeight: FontWeight.w800,
                                color: item.riskLevel == null ? ZenColors.sumi : RiskColors.forLevel(item.riskLevel!),
                              ),
                            ),
                            onTap: () => onOpen(item.id),
                          ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
