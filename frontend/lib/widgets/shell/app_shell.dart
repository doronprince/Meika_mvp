import 'package:flutter/material.dart';

import '../../core/theme/zen_theme.dart';
import '../../screens/budget_screen.dart';
import '../../screens/copilot_screen.dart';
import '../../screens/dashboard_screen.dart';
import '../../screens/price_finder_screen.dart';
import '../enso_mark.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  static const _screens = [
    DashboardScreen(),
    PriceFinderScreen(),
    BudgetScreen(),
    CopilotScreen(),
  ];

  static const _labels = ['Dashboard', 'Price-Finder', 'Budget', 'Copilot'];
  static const _icons = [
    Icons.grid_view_rounded,
    Icons.search_rounded,
    Icons.pie_chart_outline_rounded,
    Icons.forum_outlined,
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const EnsoMark(size: 28),
            const SizedBox(width: 10),
            Text(
              'Meika',
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          ],
        ),
      ),
      body: _screens[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        backgroundColor: ZenColors.washi,
        indicatorColor: ZenColors.matchaLight,
        destinations: List.generate(
          _labels.length,
          (i) => NavigationDestination(icon: Icon(_icons[i]), label: _labels[i]),
        ),
      ),
    );
  }
}
