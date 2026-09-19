import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../core/network/api_error.dart';
import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/compliance_foresight.dart';
import '../data/models/dashboard_summary.dart';
import '../data/repositories/compliance_repository.dart';
import '../providers/currency_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';
import 'goals_screen.dart' show entryCurrency;

final _day = DateFormat.yMMMd();

/// Tax & compliance foresight. The framing comes before any number: a
/// disclaimer that can't be dismissed, then what Meika can and can't see,
/// then each POSSIBLE question with the arithmetic and the assumed figure
/// behind it. There is deliberately no overall score.
class ComplianceScreen extends ConsumerWidget {
  const ComplianceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final foresight = ref.watch(complianceForesightProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tax & compliance foresight'),
        actions: [
          IconButton(
            icon: const Icon(Icons.tune_rounded),
            tooltip: 'Tax year and country',
            onPressed: () => _showSettings(context, ref),
          ),
        ],
      ),
      body: RefreshIndicator(
        color: ZenColors.matcha,
        onRefresh: () => ref.refresh(complianceForesightProvider.future),
        child: AsyncValueView<ComplianceForesight>(
          value: foresight,
          onRetry: () => ref.invalidate(complianceForesightProvider),
          builder: (context, data) => BoundedContent(
            maxWidth: 640,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
              children: [
                _DisclaimerBanner(text: data.disclaimer),
                const SizedBox(height: 12),
                _CoverageCard(data: data, onEditTaxYear: () => _showSettings(context, ref)),
                const SizedBox(height: 12),
                if (data.flags.isEmpty)
                  _NothingFlaggedCard(data: data)
                else
                  for (final flag in data.flags)
                    Padding(padding: const EdgeInsets.only(bottom: 12), child: _FlagCard(flag: flag)),
                if (data.suppressed.isNotEmpty) _SuppressedCard(rules: data.suppressed),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _showSettings(BuildContext context, WidgetRef ref) async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _SettingsSheet(),
    );
    if (saved == true) ref.invalidate(complianceForesightProvider);
  }
}

class _DisclaimerBanner extends StatelessWidget {
  final String text;

  const _DisclaimerBanner({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: ZenColors.matchaLight, borderRadius: BorderRadius.circular(10)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline_rounded, size: 18, color: ZenColors.matchaDark),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: Theme.of(context).textTheme.bodySmall)),
        ],
      ),
    );
  }
}

class _CoverageCard extends StatelessWidget {
  final ComplianceForesight data;
  final VoidCallback onEditTaxYear;

  const _CoverageCard({required this.data, required this.onEditTaxYear});

  @override
  Widget build(BuildContext context) {
    final coverage = data.coverage;
    final fy = data.fiscalWindow;
    final muted = Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('What Meika can see', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            _StatLine(label: 'Expenses logged', value: '${coverage.expenseCount}'),
            if (coverage.firstDay != null)
              _StatLine(label: 'From', value: '${_day.format(coverage.firstDay!)} (${coverage.ledgerDays} days)'),
            _StatLine(
              label: 'Tax year',
              value: '${_day.format(fy.start)} – ${_day.format(fy.end)}',
            ),
            if (fy.isDefault)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  icon: const Icon(Icons.edit_calendar_rounded, size: 16),
                  label: const Text("That's Meika's guess — set yours"),
                  onPressed: onEditTaxYear,
                ),
              ),
            const SizedBox(height: 6),
            Text("Meika can't see: ${coverage.cannotSee.join(', ')}.", style: muted),
          ],
        ),
      ),
    );
  }
}

class _NothingFlaggedCard extends StatelessWidget {
  final ComplianceForesight data;

  const _NothingFlaggedCard({required this.data});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Text(
          data.coverage.expenseCount == 0
              ? 'Meika has no expenses to look at yet. Log a few and this page will start comparing them against '
                  'the figures it assumes.'
              : 'Nothing you logged reaches any of the figures Meika is assuming. That is not the same as '
                  '"nothing to report": Meika only sees logged spending. The rules it ran are listed below.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ),
    );
  }
}

class _FlagCard extends ConsumerWidget {
  final ComplianceFlag flag;

  const _FlagCard({required this.flag});

  String get _chipLabel => switch (flag.severity) {
        RiskLevel.high => 'Possible · high',
        RiskLevel.moderate => 'Possible · moderate',
        RiskLevel.low => 'Watch',
      };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    String money(num v) => formatKrwForDisplay(ref, v);
    final color = RiskColors.forLevel(flag.severity);
    final hasFigure = flag.observedKrw != null && flag.assumedThresholdKrw != null && flag.assumptionSource != null;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
              child: Text(_chipLabel,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(color: color, fontWeight: FontWeight.w700)),
            ),
            const SizedBox(height: 10),
            Text(flag.question, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            if (hasFigure) ...[
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: LinearProgressIndicator(
                  value: flag.exposureRatio.clamp(0.0, 1.0),
                  minHeight: 10,
                  backgroundColor: ZenColors.matchaLight,
                  valueColor: AlwaysStoppedAnimation(color),
                ),
              ),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Flexible(
                    child: Text(money(flag.observedKrw!),
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w700)),
                  ),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text('assumed ${money(flag.assumedThresholdKrw!)}',
                        textAlign: TextAlign.end,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6))),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 12),
            ...flag.factors.map((f) => _FactorRow(factor: f)),
            if (hasFigure) _AssumptionActions(flag: flag),
            if (flag.evidence.isNotEmpty) _EvidenceList(flag: flag),
          ],
        ),
      ),
    );
  }
}

class _AssumptionActions extends ConsumerWidget {
  final ComplianceFlag flag;

  const _AssumptionActions({required this.flag});

  String get _provenance => switch (flag.assumptionSource) {
        AssumptionSource.userSet => 'You set this figure',
        AssumptionSource.userVerified => 'You marked this figure as checked',
        _ => "Meika's default — unverified",
      };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unverified = flag.assumptionSource == AssumptionSource.unverifiedDefault;
    return Container(
      margin: const EdgeInsets.only(top: 4, bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: unverified ? RiskColors.moderate : ZenColors.sandBorder),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(unverified ? Icons.help_outline_rounded : Icons.verified_outlined,
                  size: 16, color: unverified ? RiskColors.moderate : ZenColors.matchaDark),
              const SizedBox(width: 6),
              Expanded(
                child: Text(_provenance, style: Theme.of(context).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600)),
              ),
            ],
          ),
          Wrap(
            spacing: 4,
            children: [
              TextButton.icon(
                icon: const Icon(Icons.tune_rounded, size: 16),
                label: const Text('Change figure'),
                onPressed: () => _changeFigure(context, ref),
              ),
              if (flag.assumptionSource != AssumptionSource.userVerified)
                TextButton.icon(
                  icon: const Icon(Icons.verified_outlined, size: 16),
                  label: const Text('I checked this with a professional'),
                  onPressed: () => _run(context, ref, () => ref.read(complianceRepositoryProvider).markVerified(flag.ruleKey)),
                ),
              if (flag.assumptionSource != AssumptionSource.unverifiedDefault)
                TextButton(
                  child: const Text("Use Meika's default"),
                  onPressed: () => _run(context, ref, () => ref.read(complianceRepositoryProvider).resetRule(flag.ruleKey)),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _changeFigure(BuildContext context, WidgetRef ref) async {
    final currency = entryCurrency(ref);
    final amount = await showDialog<double>(
      context: context,
      builder: (_) => _AmountDialog(currencyCode: currency.code),
    );
    if (amount == null || !context.mounted) return;
    await _run(context, ref, () => ref.read(complianceRepositoryProvider).setThreshold(flag.ruleKey, amount / currency.rateFromKrw));
  }

  Future<void> _run(BuildContext context, WidgetRef ref, Future<void> Function() action) async {
    try {
      await action();
      ref.invalidate(complianceForesightProvider);
      ref.invalidate(complianceRulesProvider);
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }
}

class _AmountDialog extends StatefulWidget {
  final String currencyCode;

  const _AmountDialog({required this.currencyCode});

  @override
  State<_AmountDialog> createState() => _AmountDialogState();
}

class _AmountDialogState extends State<_AmountDialog> {
  final _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final value = double.tryParse(_controller.text.trim());
    if (value == null || value <= 0) {
      setState(() => _error = 'Enter an amount greater than zero');
      return;
    }
    Navigator.of(context).pop(value);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Your figure for this rule'),
      content: TextField(
        controller: _controller,
        autofocus: true,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}'))],
        decoration: InputDecoration(
          labelText: 'Amount (${widget.currencyCode})',
          helperText: 'Use the figure a professional gave you, if you have one',
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

class _EvidenceList extends ConsumerWidget {
  final ComplianceFlag flag;

  const _EvidenceList({required this.flag});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    String money(num v) => formatKrwForDisplay(ref, v);
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: Text('Evidence — ${flag.evidence.length} transaction(s)', style: Theme.of(context).textTheme.bodyMedium),
        children: [
          for (final e in flag.evidence)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(e.title),
              subtitle: Text(
                '${DateFormat.MMMd().format(e.occurredOn)}'
                '${e.originalCurrency != null ? ' · ${e.originalCurrency} ${e.originalAmount?.toStringAsFixed(2)}' : ''}',
              ),
              // The receipt tick sits where the motivation is, as the leading
              // control, so the amount keeps the trailing slot on a narrow phone.
              leading: flag.annotatable && e.expenseId != null
                  ? Checkbox(
                      value: e.hasDocumentation,
                      onChanged: (checked) async {
                        try {
                          await ref.read(complianceRepositoryProvider).setReceipt(e.expenseId!, hasReceipt: checked ?? false);
                          ref.invalidate(complianceForesightProvider);
                        } catch (err) {
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(err))));
                          }
                        }
                      },
                    )
                  : null,
              trailing: Text(money(e.amountKrw)),
            ),
          if (flag.annotatable)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('Tick an expense once you have its receipt.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6))),
            ),
        ],
      ),
    );
  }
}

class _SuppressedCard extends StatelessWidget {
  final List<SuppressedRule> rules;

  const _SuppressedCard({required this.rules});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Rules with nothing to flag (${rules.length})',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text('Each rule ran. "Nothing to flag" is not the same as "all clear".',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6))),
            const SizedBox(height: 12),
            for (final rule in rules)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(rule.title,
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
                        ),
                        Text(rule.reason.label, style: Theme.of(context).textTheme.labelSmall),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(rule.detail,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65))),
                    if (rule.daysRequired != null && rule.daysObserved != null) ...[
                      const SizedBox(height: 6),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: LinearProgressIndicator(
                          value: (rule.daysObserved! / rule.daysRequired!).clamp(0.0, 1.0),
                          minHeight: 6,
                          backgroundColor: ZenColors.matchaLight,
                          valueColor: const AlwaysStoppedAnimation(ZenColors.matcha),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SettingsSheet extends ConsumerStatefulWidget {
  const _SettingsSheet();

  @override
  ConsumerState<_SettingsSheet> createState() => _SettingsSheetState();
}

class _SettingsSheetState extends ConsumerState<_SettingsSheet> {
  final _country = TextEditingController();
  int _month = 1;
  int _day = 1;
  bool _loaded = false;
  bool _saving = false;

  @override
  void dispose() {
    _country.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final country = _country.text.trim();
    if (country.isNotEmpty && !RegExp(r'^[A-Za-z]{2}$').hasMatch(country)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Use a two-letter country code, e.g. KR')));
      return;
    }
    setState(() => _saving = true);
    try {
      await ref
          .read(complianceRepositoryProvider)
          .updateSettings(residenceJurisdiction: country, startMonth: _month, startDay: _day);
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(apiErrorMessage(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(complianceSettingsProvider);
    settings.whenData((s) {
      if (!_loaded) {
        _loaded = true;
        _country.text = s.residenceJurisdiction ?? '';
        _month = s.fiscalYearStartMonth;
        _day = s.fiscalYearStartDay;
      }
    });

    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Tax year and country', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(
            'Only used to line up the dates and phrase the referral. Meika holds no country-specific rules.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _country,
            maxLength: 2,
            textCapitalization: TextCapitalization.characters,
            decoration: const InputDecoration(labelText: 'Country you file in (optional, e.g. KR)'),
          ),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<int>(
                  key: ValueKey('month-$_month-$_loaded'),
                  initialValue: _month,
                  decoration: const InputDecoration(labelText: 'Tax year starts in'),
                  items: [
                    for (var m = 1; m <= 12; m++)
                      DropdownMenuItem(value: m, child: Text(DateFormat.MMMM().format(DateTime(2026, m)))),
                  ],
                  onChanged: (m) => setState(() => _month = m ?? 1),
                ),
              ),
              const SizedBox(width: 12),
              SizedBox(
                width: 90,
                child: DropdownButtonFormField<int>(
                  key: ValueKey('day-$_day-$_loaded'),
                  initialValue: _day,
                  decoration: const InputDecoration(labelText: 'Day'),
                  items: [for (var d = 1; d <= 31; d++) DropdownMenuItem(value: d, child: Text('$d'))],
                  onChanged: (d) => setState(() => _day = d ?? 1),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Text('Save'),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatLine extends StatelessWidget {
  final String label;
  final String value;

  const _StatLine({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.7))),
          Flexible(
            child: Text(value,
                textAlign: TextAlign.end,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600)),
          ),
        ],
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
          Text(factor.detail,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.65))),
        ],
      ),
    );
  }
}
