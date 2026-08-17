import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/zen_theme.dart';

/// Consistent loading/error chrome for screens backed by a [FutureProvider].
/// Keeps the "honest empty/error state, no fabricated data" rule in one
/// place instead of re-implemented per screen.
class AsyncValueView<T> extends StatelessWidget {
  final AsyncValue<T> value;
  final Widget Function(BuildContext context, T data) builder;
  final VoidCallback? onRetry;

  const AsyncValueView({super.key, required this.value, required this.builder, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return value.when(
      data: (data) => builder(context, data),
      loading: () => const Center(child: CircularProgressIndicator(color: ZenColors.matcha)),
      error: (error, _) => Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.cloud_off_rounded, color: ZenColors.sumi.withValues(alpha: 0.4), size: 40),
              const SizedBox(height: 12),
              Text(
                "Couldn't reach Meika's backend",
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              Text(
                error.toString(),
                textAlign: TextAlign.center,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
              ),
              if (onRetry != null) ...[
                const SizedBox(height: 16),
                OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
