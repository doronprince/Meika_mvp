import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/auth_token_provider.dart';
import '../../core/theme/zen_theme.dart';
import '../../providers/currency_providers.dart';
import '../../screens/budget_screen.dart';
import '../../screens/copilot_screen.dart';
import '../../screens/dashboard_screen.dart';
import '../../screens/price_finder_screen.dart';
import '../currency_picker.dart';
import '../enso_mark.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
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
        actions: [
          TextButton.icon(
            icon: const Icon(Icons.currency_exchange_rounded, size: 18),
            label: Text(ref.watch(preferredCurrencyProvider)),
            style: TextButton.styleFrom(foregroundColor: ZenColors.sumi),
            onPressed: () => showCurrencyPicker(context, ref),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            tooltip: 'Log out',
            onPressed: () => ref.read(authTokenProvider.notifier).state = null,
          ),
        ],
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
