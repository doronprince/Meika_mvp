import 'package:flutter/material.dart';

import '../widgets/coming_soon.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const ComingSoon(
      title: 'Dashboard',
      subtitle: 'Predictive Budgeting & Financial Clarity Score — arrives in Phase 6.',
    );
  }
}
