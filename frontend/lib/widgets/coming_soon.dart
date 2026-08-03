import 'package:flutter/material.dart';

import '../core/theme/zen_theme.dart';
import 'enso_mark.dart';

/// Honest placeholder for screens not yet wired to real data — states which
/// phase delivers them instead of showing fabricated content.
class ComingSoon extends StatelessWidget {
  final String title;
  final String subtitle;

  const ComingSoon({super.key, required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const EnsoMark(size: 56),
            const SizedBox(height: 20),
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .headlineSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: ZenColors.sumi.withValues(alpha: 0.6),
                  ),
            ),
          ],
        ),
      ),
    );
  }
}
