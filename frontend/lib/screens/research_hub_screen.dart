import 'package:flutter/material.dart';

import '../core/theme/zen_theme.dart';
import '../widgets/bounded_content.dart';
import 'survival_screen.dart';

/// Entry point for the research modules that look ahead of the user's
/// current numbers. A module without a working screen is listed as in
/// progress, never as a mock-up with invented figures.
class ResearchHubScreen extends StatelessWidget {
  const ResearchHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BoundedContent(
      maxWidth: 640,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          Text('Foresight', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(
            'Looking ahead of your current numbers. Every figure comes with the arithmetic behind it.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.7)),
          ),
          const SizedBox(height: 16),
          _ModuleTile(
            icon: Icons.shield_outlined,
            title: 'Survival runway',
            subtitle: 'How long your savings last when several shocks hit at once, and which one does the damage.',
            builder: (_) => const SurvivalScreen(),
          ),
          const _ModuleTile(
            icon: Icons.sensors_rounded,
            title: 'Early warning',
            subtitle: 'Leading signs of financial strain, before they show up in your budget.',
          ),
          const _ModuleTile(
            icon: Icons.receipt_long_outlined,
            title: 'Tax & compliance foresight',
            subtitle: 'Spending today that could become a tax or reporting question months from now.',
          ),
          const _ModuleTile(
            icon: Icons.phone_iphone_rounded,
            title: 'Exposure & spending',
            subtitle: 'Whether time on shopping feeds lines up with spending spikes, with a nudge before they happen.',
          ),
          const _ModuleTile(
            icon: Icons.fact_check_outlined,
            title: 'Claim check',
            subtitle: 'Weigh a money claim you saw online: sources, conflicts of interest, and what it means for you.',
          ),
        ],
      ),
    );
  }
}

class _ModuleTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  /// Null while the module's screen isn't built yet.
  final WidgetBuilder? builder;

  const _ModuleTile({required this.icon, required this.title, required this.subtitle, this.builder});

  @override
  Widget build(BuildContext context) {
    final available = builder != null;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor: available ? ZenColors.matchaLight : ZenColors.sandBorder,
          child: Icon(icon, color: available ? ZenColors.matchaDark : ZenColors.sumi.withValues(alpha: 0.4)),
        ),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(subtitle),
        ),
        trailing: available
            ? const Icon(Icons.chevron_right_rounded)
            : Text('In progress', style: Theme.of(context).textTheme.labelSmall),
        onTap: available ? () => Navigator.of(context).push(MaterialPageRoute(builder: builder!)) : null,
      ),
    );
  }
}
