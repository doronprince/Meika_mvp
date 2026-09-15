import 'dashboard_summary.dart';
import 'expense_category.dart';

double? _nullableAmount(dynamic value) => value == null ? null : parseAmount(value);

class RunwayResult {
  final double? months;
  final int? days;

  /// Savings never run out within the simulated horizon.
  final bool sustainable;

  const RunwayResult({required this.months, required this.days, required this.sustainable});

  factory RunwayResult.fromJson(Map<String, dynamic> json) {
    return RunwayResult(
      months: _nullableAmount(json['months']),
      days: json['days'] as int?,
      sustainable: json['sustainable_within_horizon'] as bool,
    );
  }
}

class ShockAttribution {
  final int shockIndex;
  final String label;
  final String kind;

  /// Exact Shapley value — these sum to the joint runway loss.
  final double monthsLost;
  final double standaloneMonthsLost;
  final double? sharePct;

  const ShockAttribution({
    required this.shockIndex,
    required this.label,
    required this.kind,
    required this.monthsLost,
    required this.standaloneMonthsLost,
    required this.sharePct,
  });

  factory ShockAttribution.fromJson(Map<String, dynamic> json) {
    return ShockAttribution(
      shockIndex: json['shock_index'] as int,
      label: json['label'] as String,
      kind: json['kind'] as String,
      monthsLost: parseAmount(json['months_lost']),
      standaloneMonthsLost: parseAmount(json['standalone_months_lost']),
      sharePct: _nullableAmount(json['share_pct']),
    );
  }
}

class TrajectoryPoint {
  final int month;
  final double baselineKrw;
  final double shockedKrw;
  final double withCutsKrw;

  const TrajectoryPoint({
    required this.month,
    required this.baselineKrw,
    required this.shockedKrw,
    required this.withCutsKrw,
  });

  factory TrajectoryPoint.fromJson(Map<String, dynamic> json) {
    return TrajectoryPoint(
      month: json['month'] as int,
      baselineKrw: parseAmount(json['baseline_balance_krw']),
      shockedKrw: parseAmount(json['shocked_balance_krw']),
      withCutsKrw: parseAmount(json['shocked_with_cuts_balance_krw']),
    );
  }
}

class SpendBaseline {
  final double monthlyIncomeKrw;
  final double monthlyEssentialKrw;
  final double monthlyDiscretionaryKrw;
  final double monthlyNetKrw;
  final String spendSource;
  final int ledgerDays;
  final int incomeStreamsCounted;

  const SpendBaseline({
    required this.monthlyIncomeKrw,
    required this.monthlyEssentialKrw,
    required this.monthlyDiscretionaryKrw,
    required this.monthlyNetKrw,
    required this.spendSource,
    required this.ledgerDays,
    required this.incomeStreamsCounted,
  });

  factory SpendBaseline.fromJson(Map<String, dynamic> json) {
    return SpendBaseline(
      monthlyIncomeKrw: parseAmount(json['monthly_income_krw']),
      monthlyEssentialKrw: parseAmount(json['monthly_essential_krw']),
      monthlyDiscretionaryKrw: parseAmount(json['monthly_discretionary_krw']),
      monthlyNetKrw: parseAmount(json['monthly_net_krw']),
      spendSource: json['spend_source'] as String,
      ledgerDays: json['ledger_days'] as int,
      incomeStreamsCounted: json['income_streams_counted'] as int,
    );
  }
}

class SurvivalReport {
  final String state;
  final int horizonMonths;
  final double? liquidSavingsKrw;
  final SpendBaseline baseline;
  final RunwayResult? baselineRunway;
  final RunwayResult? shockedRunway;
  final RunwayResult? withCutsRunway;
  final int? cutsStartMonth;
  final RiskLevel? riskLevel;
  final List<ShockAttribution> attributions;
  final double? jointMonthsLost;
  final double? interactionMonths;
  final double? attributionResidualMonths;
  final List<TrajectoryPoint> trajectory;
  final List<ClarityFactor> factors;
  final List<String> assumptions;

  const SurvivalReport({
    required this.state,
    required this.horizonMonths,
    required this.liquidSavingsKrw,
    required this.baseline,
    required this.baselineRunway,
    required this.shockedRunway,
    required this.withCutsRunway,
    required this.cutsStartMonth,
    required this.riskLevel,
    required this.attributions,
    required this.jointMonthsLost,
    required this.interactionMonths,
    required this.attributionResidualMonths,
    required this.trajectory,
    required this.factors,
    required this.assumptions,
  });

  bool get needsSavings => state == 'needs_savings';

  factory SurvivalReport.fromJson(Map<String, dynamic> json) {
    RunwayResult? runway(String key) =>
        json[key] == null ? null : RunwayResult.fromJson(json[key] as Map<String, dynamic>);

    return SurvivalReport(
      state: json['state'] as String,
      horizonMonths: json['horizon_months'] as int,
      liquidSavingsKrw: _nullableAmount(json['liquid_savings_krw']),
      baseline: SpendBaseline.fromJson(json['baseline'] as Map<String, dynamic>),
      baselineRunway: runway('baseline_runway'),
      shockedRunway: runway('shocked_runway'),
      withCutsRunway: runway('shocked_with_cuts_runway'),
      cutsStartMonth: json['cuts_start_month'] as int?,
      riskLevel: json['risk_level'] == null ? null : RiskLevel.fromJson(json['risk_level'] as String),
      attributions: (json['attributions'] as List)
          .map((a) => ShockAttribution.fromJson(a as Map<String, dynamic>))
          .toList(),
      jointMonthsLost: _nullableAmount(json['joint_months_lost']),
      interactionMonths: _nullableAmount(json['interaction_months']),
      attributionResidualMonths: _nullableAmount(json['attribution_residual_months']),
      trajectory: (json['trajectory'] as List)
          .map((p) => TrajectoryPoint.fromJson(p as Map<String, dynamic>))
          .toList(),
      factors: (json['factors'] as List).map((f) => ClarityFactor.fromJson(f as Map<String, dynamic>)).toList(),
      assumptions: (json['assumptions'] as List).cast<String>(),
    );
  }
}

class ShockPreset {
  final String key;
  final String title;
  final String description;

  /// Sent back verbatim (magnitude possibly edited) in a simulate request.
  final Map<String, dynamic> shock;

  const ShockPreset({required this.key, required this.title, required this.description, required this.shock});

  factory ShockPreset.fromJson(Map<String, dynamic> json) {
    return ShockPreset(
      key: json['key'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      shock: Map<String, dynamic>.from(json['shock'] as Map),
    );
  }
}
