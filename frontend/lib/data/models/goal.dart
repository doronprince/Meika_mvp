import 'dashboard_summary.dart';
import 'expense_category.dart';

/// Mirrors the backend's `GoalType` enum values byte-for-byte.
enum GoalType {
  savings,
  spendingCap;

  String get wireValue => this == GoalType.savings ? 'savings' : 'spending_cap';

  static GoalType fromJson(String value) => value == 'spending_cap' ? GoalType.spendingCap : GoalType.savings;
}

/// Computed server-side on every read (backend app/services/goal_forecast.py)
/// — the client never derives a verdict itself.
enum GoalVerdict {
  onTrack('on_track', 'On track'),
  atRisk('at_risk', 'At risk'),
  offTrack('off_track', 'Off track'),
  achieved('achieved', 'Achieved'),
  missed('missed', 'Missed'),
  insufficientData('insufficient_data', 'Too early to tell');

  final String wireValue;
  final String label;

  const GoalVerdict(this.wireValue, this.label);

  static GoalVerdict fromJson(String value) {
    return GoalVerdict.values.firstWhere((v) => v.wireValue == value, orElse: () => GoalVerdict.insufficientData);
  }
}

double? _nullableAmount(dynamic value) => value == null ? null : parseAmount(value);

class GoalForecast {
  final GoalVerdict verdict;
  final double progressKrw;
  final double progressPercent;
  final int daysElapsed;
  final int daysTotal;
  final int daysRemaining;
  final double paceKrwPerDay;
  final double? projectedFinalKrw;
  final double? requiredKrwPerDay;
  final double? requiredChangeKrwPerDay;

  /// Same shape as the Clarity Score's factors — the XAI reasoning behind
  /// [verdict]. Never render the verdict without these.
  final List<ClarityFactor> factors;

  const GoalForecast({
    required this.verdict,
    required this.progressKrw,
    required this.progressPercent,
    required this.daysElapsed,
    required this.daysTotal,
    required this.daysRemaining,
    required this.paceKrwPerDay,
    required this.projectedFinalKrw,
    required this.requiredKrwPerDay,
    required this.requiredChangeKrwPerDay,
    required this.factors,
  });

  factory GoalForecast.fromJson(Map<String, dynamic> json) {
    return GoalForecast(
      verdict: GoalVerdict.fromJson(json['verdict'] as String),
      progressKrw: parseAmount(json['progress_krw']),
      progressPercent: parseAmount(json['progress_percent']),
      daysElapsed: json['days_elapsed'] as int,
      daysTotal: json['days_total'] as int,
      daysRemaining: json['days_remaining'] as int,
      paceKrwPerDay: parseAmount(json['pace_krw_per_day']),
      projectedFinalKrw: _nullableAmount(json['projected_final_krw']),
      requiredKrwPerDay: _nullableAmount(json['required_krw_per_day']),
      requiredChangeKrwPerDay: _nullableAmount(json['required_change_krw_per_day']),
      factors: (json['factors'] as List).map((f) => ClarityFactor.fromJson(f as Map<String, dynamic>)).toList(),
    );
  }
}

class Goal {
  final String id;
  final String name;
  final GoalType goalType;
  final double targetAmountKrw;
  final double startingAmountKrw;
  final ExpenseCategory? category;
  final DateTime startDate;
  final DateTime targetDate;
  final GoalForecast forecast;

  const Goal({
    required this.id,
    required this.name,
    required this.goalType,
    required this.targetAmountKrw,
    required this.startingAmountKrw,
    required this.category,
    required this.startDate,
    required this.targetDate,
    required this.forecast,
  });

  factory Goal.fromJson(Map<String, dynamic> json) {
    return Goal(
      id: json['id'] as String,
      name: json['name'] as String,
      goalType: GoalType.fromJson(json['goal_type'] as String),
      targetAmountKrw: parseAmount(json['target_amount_krw']),
      startingAmountKrw: parseAmount(json['starting_amount_krw']),
      category: json['category'] == null ? null : ExpenseCategory.fromJson(json['category'] as String),
      startDate: DateTime.parse(json['start_date'] as String),
      targetDate: DateTime.parse(json['target_date'] as String),
      forecast: GoalForecast.fromJson(json['forecast'] as Map<String, dynamic>),
    );
  }
}
