import 'expense_category.dart';

/// Mirrors the backend's `IncomeKind` enum values byte-for-byte.
enum IncomeKind {
  salary('salary', 'Salary'),
  partTime('part_time', 'Part-time work'),
  freelance('freelance', 'Freelance'),
  scholarship('scholarship', 'Scholarship'),
  familySupport('family_support', 'Family support'),
  other('other', 'Other');

  final String wireValue;
  final String displayName;

  const IncomeKind(this.wireValue, this.displayName);

  static IncomeKind fromJson(String value) {
    return IncomeKind.values.firstWhere((k) => k.wireValue == value, orElse: () => IncomeKind.other);
  }
}

class IncomeStream {
  final String id;
  final String label;
  final IncomeKind kind;

  /// In [currency], the currency the income is actually paid in.
  final double monthlyAmount;
  final String currency;
  final double monthlyAmountKrwSnapshot;
  final bool isActive;

  const IncomeStream({
    required this.id,
    required this.label,
    required this.kind,
    required this.monthlyAmount,
    required this.currency,
    required this.monthlyAmountKrwSnapshot,
    required this.isActive,
  });

  factory IncomeStream.fromJson(Map<String, dynamic> json) {
    return IncomeStream(
      id: json['id'] as String,
      label: json['label'] as String,
      kind: IncomeKind.fromJson(json['kind'] as String),
      monthlyAmount: parseAmount(json['monthly_amount']),
      currency: json['currency'] as String,
      monthlyAmountKrwSnapshot: parseAmount(json['monthly_amount_krw_snapshot']),
      isActive: json['is_active'] as bool,
    );
  }
}
