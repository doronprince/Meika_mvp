import 'expense_category.dart';

class Expense {
  final String id;
  final String title;
  final ExpenseCategory category;
  final double amountKrw;
  final String? storeName;
  final double transitCostKrw;
  final DateTime occurredOn;
  final double totalEconomicCostKrw;
  final String? originalCurrency;
  final double? originalAmount;

  const Expense({
    required this.id,
    required this.title,
    required this.category,
    required this.amountKrw,
    required this.storeName,
    required this.transitCostKrw,
    required this.occurredOn,
    required this.totalEconomicCostKrw,
    required this.originalCurrency,
    required this.originalAmount,
  });

  factory Expense.fromJson(Map<String, dynamic> json) {
    return Expense(
      id: json['id'] as String,
      title: json['title'] as String,
      category: ExpenseCategory.fromJson(json['category'] as String),
      amountKrw: parseAmount(json['amount_krw']),
      storeName: json['store_name'] as String?,
      transitCostKrw: parseAmount(json['transit_cost_krw']),
      occurredOn: DateTime.parse(json['occurred_on'] as String),
      totalEconomicCostKrw: parseAmount(json['total_economic_cost_krw']),
      originalCurrency: json['original_currency'] as String?,
      originalAmount: json['original_amount'] == null ? null : parseAmount(json['original_amount']),
    );
  }
}
