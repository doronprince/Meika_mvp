import 'package:flutter/material.dart';

import '../widgets/coming_soon.dart';

class BudgetScreen extends StatelessWidget {
  const BudgetScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ComingSoon(
      title: 'Budget',
      subtitle: 'Expense history, spending velocity, and cash-flow risk — arrives in Phase 6.',
    );
  }
}
