/// Mirrors the backend's `ExpenseCategory` enum values byte-for-byte.
enum ExpenseCategory {
  groceries,
  cafesAndDining,
  transportation,
  housingAndUtilities,
  education,
  apparel,
  electronics,
  other;

  static ExpenseCategory fromJson(String value) {
    return ExpenseCategory.values.firstWhere(
      (c) => c.wireValue == value,
      orElse: () => ExpenseCategory.other,
    );
  }

  String get wireValue {
    switch (this) {
      case ExpenseCategory.groceries:
        return 'groceries';
      case ExpenseCategory.cafesAndDining:
        return 'cafes_and_dining';
      case ExpenseCategory.transportation:
        return 'transportation';
      case ExpenseCategory.housingAndUtilities:
        return 'housing_and_utilities';
      case ExpenseCategory.education:
        return 'education';
      case ExpenseCategory.apparel:
        return 'apparel';
      case ExpenseCategory.electronics:
        return 'electronics';
      case ExpenseCategory.other:
        return 'other';
    }
  }

  String get displayName {
    switch (this) {
      case ExpenseCategory.groceries:
        return 'Groceries';
      case ExpenseCategory.cafesAndDining:
        return 'Cafes & Dining';
      case ExpenseCategory.transportation:
        return 'Transportation';
      case ExpenseCategory.housingAndUtilities:
        return 'Housing & Utilities';
      case ExpenseCategory.education:
        return 'Education';
      case ExpenseCategory.apparel:
        return 'Apparel';
      case ExpenseCategory.electronics:
        return 'Electronics';
      case ExpenseCategory.other:
        return 'Other';
    }
  }
}

/// Parses a JSON value that may arrive as a string, int, or double —
/// pydantic's Decimal encoding varies by field/version, so every money or
/// percentage field on the wire goes through this instead of a bare cast.
double parseAmount(dynamic value) {
  if (value == null) return 0;
  if (value is num) return value.toDouble();
  return double.parse(value.toString());
}
