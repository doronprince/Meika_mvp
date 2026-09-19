import 'dashboard_summary.dart';
import 'expense_category.dart';

/// Where a rule's assumed figure came from. `userVerified` records a claim
/// the user made, not a check Meika performed.
enum AssumptionSource {
  unverifiedDefault('unverified_default'),
  userSet('user_set'),
  userVerified('user_verified');

  final String wireValue;

  const AssumptionSource(this.wireValue);

  static AssumptionSource? fromJson(String? value) {
    if (value == null) return null;
    return AssumptionSource.values.firstWhere((s) => s.wireValue == value, orElse: () => AssumptionSource.unverifiedDefault);
  }
}

enum SuppressionReason {
  noLedger('no_ledger', 'No expenses yet'),
  insufficientHistory('insufficient_history', 'Needs more history'),
  noMatchingTransactions('no_matching_transactions', 'Nothing matched'),
  belowEmissionBand('below_emission_band', 'Checked, nothing to flag'),
  ruleDisabledByUser('rule_disabled_by_user', 'Turned off'),
  ruleSpecInvalid('rule_spec_invalid', 'Rule could not be read'),
  unknown('unknown', 'Not evaluated');

  final String wireValue;
  final String label;

  const SuppressionReason(this.wireValue, this.label);

  static SuppressionReason fromJson(String value) {
    return SuppressionReason.values.firstWhere((r) => r.wireValue == value, orElse: () => SuppressionReason.unknown);
  }
}

DateTime? _date(dynamic value) => value == null ? null : DateTime.parse(value as String);
double? _amount(dynamic value) => value == null ? null : parseAmount(value);

class FlagEvidence {
  final String? expenseId;
  final DateTime occurredOn;
  final String title;
  final double amountKrw;
  final String? originalCurrency;
  final double? originalAmount;
  final bool hasDocumentation;

  const FlagEvidence({
    required this.expenseId,
    required this.occurredOn,
    required this.title,
    required this.amountKrw,
    required this.originalCurrency,
    required this.originalAmount,
    required this.hasDocumentation,
  });

  factory FlagEvidence.fromJson(Map<String, dynamic> json) {
    return FlagEvidence(
      expenseId: json['expense_id'] as String?,
      occurredOn: DateTime.parse(json['occurred_on'] as String),
      title: json['title'] as String,
      amountKrw: parseAmount(json['amount_krw']),
      originalCurrency: json['original_currency'] as String?,
      originalAmount: _amount(json['original_amount']),
      hasDocumentation: json['has_documentation'] as bool,
    );
  }
}

class ComplianceFlag {
  final String ruleKey;
  final String title;
  final String question;
  final RiskLevel severity;
  final double exposureRatio;
  final double? observedKrw;
  final double? assumedThresholdKrw;
  final AssumptionSource? assumptionSource;
  final DateTime? crossedOn;
  final DateTime? crossEarliestOn;
  final DateTime? crossLatestOn;

  /// Always ends with the professional-referral factor (appended by the
  /// backend in code). Never render the flag without these.
  final List<ClarityFactor> factors;
  final List<FlagEvidence> evidence;
  final bool annotatable;

  const ComplianceFlag({
    required this.ruleKey,
    required this.title,
    required this.question,
    required this.severity,
    required this.exposureRatio,
    required this.observedKrw,
    required this.assumedThresholdKrw,
    required this.assumptionSource,
    required this.crossedOn,
    required this.crossEarliestOn,
    required this.crossLatestOn,
    required this.factors,
    required this.evidence,
    required this.annotatable,
  });

  factory ComplianceFlag.fromJson(Map<String, dynamic> json) {
    return ComplianceFlag(
      ruleKey: json['rule_key'] as String,
      title: json['title'] as String,
      question: json['question'] as String,
      severity: RiskLevel.fromJson(json['severity'] as String),
      exposureRatio: parseAmount(json['exposure_ratio']),
      observedKrw: _amount(json['observed_krw']),
      assumedThresholdKrw: _amount(json['assumed_threshold_krw']),
      assumptionSource: AssumptionSource.fromJson(json['assumption_source'] as String?),
      crossedOn: _date(json['crossed_on']),
      crossEarliestOn: _date(json['cross_earliest_on']),
      crossLatestOn: _date(json['cross_latest_on']),
      factors: (json['factors'] as List).map((f) => ClarityFactor.fromJson(f as Map<String, dynamic>)).toList(),
      evidence: (json['evidence'] as List).map((e) => FlagEvidence.fromJson(e as Map<String, dynamic>)).toList(),
      annotatable: json['annotatable'] as bool? ?? false,
    );
  }
}

class SuppressedRule {
  final String ruleKey;
  final String title;
  final SuppressionReason reason;
  final String detail;
  final int? daysObserved;
  final int? daysRequired;

  const SuppressedRule({
    required this.ruleKey,
    required this.title,
    required this.reason,
    required this.detail,
    required this.daysObserved,
    required this.daysRequired,
  });

  factory SuppressedRule.fromJson(Map<String, dynamic> json) {
    return SuppressedRule(
      ruleKey: json['rule_key'] as String,
      title: json['title'] as String,
      reason: SuppressionReason.fromJson(json['reason'] as String),
      detail: json['detail'] as String,
      daysObserved: json['days_observed'] as int?,
      daysRequired: json['days_required'] as int?,
    );
  }
}

class LedgerCoverage {
  final int expenseCount;
  final DateTime? firstDay;
  final int ledgerDays;
  final List<String> cannotSee;

  const LedgerCoverage({required this.expenseCount, required this.firstDay, required this.ledgerDays, required this.cannotSee});

  factory LedgerCoverage.fromJson(Map<String, dynamic> json) {
    return LedgerCoverage(
      expenseCount: json['expense_count'] as int,
      firstDay: _date(json['first_day']),
      ledgerDays: json['ledger_days'] as int,
      cannotSee: (json['cannot_see'] as List).cast<String>(),
    );
  }
}

class FiscalWindow {
  final DateTime start;
  final DateTime end;
  final int daysRemaining;
  final bool isDefault;

  const FiscalWindow({required this.start, required this.end, required this.daysRemaining, required this.isDefault});

  factory FiscalWindow.fromJson(Map<String, dynamic> json) {
    return FiscalWindow(
      start: DateTime.parse(json['start'] as String),
      end: DateTime.parse(json['end'] as String),
      daysRemaining: json['days_remaining'] as int,
      isDefault: json['is_default'] as bool,
    );
  }
}

class ComplianceForesight {
  final DateTime asOf;
  final List<ComplianceFlag> flags;
  final List<SuppressedRule> suppressed;
  final int rulesEvaluated;
  final LedgerCoverage coverage;
  final FiscalWindow fiscalWindow;
  final String disclaimer;

  const ComplianceForesight({
    required this.asOf,
    required this.flags,
    required this.suppressed,
    required this.rulesEvaluated,
    required this.coverage,
    required this.fiscalWindow,
    required this.disclaimer,
  });

  factory ComplianceForesight.fromJson(Map<String, dynamic> json) {
    return ComplianceForesight(
      asOf: DateTime.parse(json['as_of'] as String),
      flags: (json['flags'] as List).map((f) => ComplianceFlag.fromJson(f as Map<String, dynamic>)).toList(),
      suppressed: (json['suppressed'] as List).map((s) => SuppressedRule.fromJson(s as Map<String, dynamic>)).toList(),
      rulesEvaluated: (json['counts'] as Map<String, dynamic>)['rules_evaluated'] as int,
      coverage: LedgerCoverage.fromJson(json['coverage'] as Map<String, dynamic>),
      fiscalWindow: FiscalWindow.fromJson(json['fiscal_window'] as Map<String, dynamic>),
      disclaimer: json['disclaimer'] as String,
    );
  }
}

class ComplianceRuleView {
  final String ruleKey;
  final String title;
  final double? effectiveThresholdKrw;
  final double? packagedThresholdKrw;
  final String? thresholdBasisNote;
  final String assumptionStatement;
  final String verificationPrompt;
  final String sourceNote;
  final AssumptionSource assumptionSource;
  final bool isEnabled;
  final DateTime? verifiedAt;

  const ComplianceRuleView({
    required this.ruleKey,
    required this.title,
    required this.effectiveThresholdKrw,
    required this.packagedThresholdKrw,
    required this.thresholdBasisNote,
    required this.assumptionStatement,
    required this.verificationPrompt,
    required this.sourceNote,
    required this.assumptionSource,
    required this.isEnabled,
    required this.verifiedAt,
  });

  factory ComplianceRuleView.fromJson(Map<String, dynamic> json) {
    return ComplianceRuleView(
      ruleKey: json['rule_key'] as String,
      title: json['title'] as String,
      effectiveThresholdKrw: _amount(json['effective_threshold_krw']),
      packagedThresholdKrw: _amount(json['packaged_threshold_krw']),
      thresholdBasisNote: json['threshold_basis_note'] as String?,
      assumptionStatement: json['assumption_statement'] as String,
      verificationPrompt: json['verification_prompt'] as String,
      sourceNote: json['source_note'] as String,
      assumptionSource: AssumptionSource.fromJson(json['assumption_source'] as String) ?? AssumptionSource.unverifiedDefault,
      isEnabled: json['is_enabled'] as bool,
      verifiedAt: _date(json['verified_at']),
    );
  }
}

class ComplianceSettings {
  final String? residenceJurisdiction;
  final int fiscalYearStartMonth;
  final int fiscalYearStartDay;
  final bool isDefault;

  const ComplianceSettings({
    required this.residenceJurisdiction,
    required this.fiscalYearStartMonth,
    required this.fiscalYearStartDay,
    required this.isDefault,
  });

  factory ComplianceSettings.fromJson(Map<String, dynamic> json) {
    return ComplianceSettings(
      residenceJurisdiction: json['residence_jurisdiction'] as String?,
      fiscalYearStartMonth: json['fiscal_year_start_month'] as int,
      fiscalYearStartDay: json['fiscal_year_start_day'] as int,
      isDefault: json['is_default'] as bool,
    );
  }
}
