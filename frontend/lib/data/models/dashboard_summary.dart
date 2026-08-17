import 'expense_category.dart';

enum RiskLevel { low, moderate, high;

  static RiskLevel fromJson(String value) {
    return RiskLevel.values.firstWhere((r) => r.name == value, orElse: () => RiskLevel.moderate);
  }
}

class ClarityFactor {
  final String label;
  final String detail;
  final double? value;

  const ClarityFactor({required this.label, required this.detail, this.value});

  factory ClarityFactor.fromJson(Map<String, dynamic> json) {
    return ClarityFactor(
      label: json['label'] as String,
      detail: json['detail'] as String,
      value: json['value'] == null ? null : parseAmount(json['value']),
    );
  }
}

class ClarityScore {
  final int value;
  final RiskLevel riskLevel;
  final List<ClarityFactor> factors;

  const ClarityScore({required this.value, required this.riskLevel, required this.factors});

  factory ClarityScore.fromJson(Map<String, dynamic> json) {
    return ClarityScore(
      value: json['value'] as int,
      riskLevel: RiskLevel.fromJson(json['risk_level'] as String),
      factors: (json['factors'] as List)
          .map((f) => ClarityFactor.fromJson(f as Map<String, dynamic>))
          .toList(),
    );
  }
}

class CategoryBreakdownItem {
  final ExpenseCategory category;
  final double totalKrw;
  final double percentOfSpend;

  const CategoryBreakdownItem({
    required this.category,
    required this.totalKrw,
    required this.percentOfSpend,
  });

  factory CategoryBreakdownItem.fromJson(Map<String, dynamic> json) {
    return CategoryBreakdownItem(
      category: ExpenseCategory.fromJson(json['category'] as String),
      totalKrw: parseAmount(json['total_krw']),
      percentOfSpend: parseAmount(json['percent_of_spend']),
    );
  }
}

class DashboardSummary {
  final double monthlyBudgetKrw;
  final double totalSpentThisMonthKrw;
  final double remainingBudgetKrw;
  final int daysElapsedThisMonth;
  final int daysInMonth;
  final double spendingVelocityKrwPerDay;
  final double? projectedMonthEndSpendKrw;
  final double? projectedOverageKrw;
  final List<CategoryBreakdownItem> categoryBreakdown;
  final ClarityScore clarityScore;

  const DashboardSummary({
    required this.monthlyBudgetKrw,
    required this.totalSpentThisMonthKrw,
    required this.remainingBudgetKrw,
    required this.daysElapsedThisMonth,
    required this.daysInMonth,
    required this.spendingVelocityKrwPerDay,
    required this.projectedMonthEndSpendKrw,
    required this.projectedOverageKrw,
    required this.categoryBreakdown,
    required this.clarityScore,
  });

  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    return DashboardSummary(
      monthlyBudgetKrw: parseAmount(json['monthly_budget_krw']),
      totalSpentThisMonthKrw: parseAmount(json['total_spent_this_month_krw']),
      remainingBudgetKrw: parseAmount(json['remaining_budget_krw']),
      daysElapsedThisMonth: json['days_elapsed_this_month'] as int,
      daysInMonth: json['days_in_month'] as int,
      spendingVelocityKrwPerDay: parseAmount(json['spending_velocity_krw_per_day']),
      projectedMonthEndSpendKrw: json['projected_month_end_spend_krw'] == null
          ? null
          : parseAmount(json['projected_month_end_spend_krw']),
      projectedOverageKrw:
          json['projected_overage_krw'] == null ? null : parseAmount(json['projected_overage_krw']),
      categoryBreakdown: (json['category_breakdown'] as List)
          .map((c) => CategoryBreakdownItem.fromJson(c as Map<String, dynamic>))
          .toList(),
      clarityScore: ClarityScore.fromJson(json['clarity_score'] as Map<String, dynamic>),
    );
  }
}
