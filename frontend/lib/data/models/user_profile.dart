import 'expense_category.dart';

class UserProfile {
  final String id;
  final String email;
  final String? fullName;
  final double monthlyBudgetKrw;
  final String preferredCurrency;

  /// Null means the user hasn't told us, which is not the same as zero.
  final double? liquidSavingsKrw;

  const UserProfile({
    required this.id,
    required this.email,
    required this.fullName,
    required this.monthlyBudgetKrw,
    required this.preferredCurrency,
    this.liquidSavingsKrw,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as String,
      email: json['email'] as String,
      fullName: json['full_name'] as String?,
      monthlyBudgetKrw: parseAmount(json['monthly_budget_krw']),
      preferredCurrency: json['preferred_currency'] as String,
      liquidSavingsKrw: json['liquid_savings_krw'] == null ? null : parseAmount(json['liquid_savings_krw']),
    );
  }
}
