import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/zen_theme.dart';
import '../data/models/price_finder_result.dart';
import '../providers/currency_providers.dart';
import '../providers/price_finder_providers.dart';
import '../widgets/async_value_view.dart';
import '../widgets/bounded_content.dart';

class PriceFinderScreen extends ConsumerStatefulWidget {
  const PriceFinderScreen({super.key});

  @override
  ConsumerState<PriceFinderScreen> createState() => _PriceFinderScreenState();
}

class _PriceFinderScreenState extends ConsumerState<PriceFinderScreen> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: ref.read(priceFinderQueryProvider));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit(String value) {
    ref.read(priceFinderQueryProvider.notifier).state = value.trim();
  }

  @override
  Widget build(BuildContext context) {
    final results = ref.watch(priceFinderResultsProvider);

    return BoundedContent(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: TextField(
              controller: _controller,
              textInputAction: TextInputAction.search,
              onSubmitted: _submit,
              decoration: InputDecoration(
                hintText: 'Search a product (e.g. Rice, Ramen, Milk)…',
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: _controller.text.isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(Icons.clear_rounded),
                        onPressed: () {
                          _controller.clear();
                          _submit('');
                        },
                      ),
                filled: true,
                fillColor: ZenColors.cardBg,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: ZenColors.sandBorder),
                ),
              ),
            ),
          ),
          Expanded(
            child: AsyncValueView<List<PriceFinderResult>>(
              value: results,
              onRetry: () => ref.invalidate(priceFinderResultsProvider),
              builder: (context, items) => _ResultsList(items: items),
            ),
          ),
        ],
      ),
    );
  }
}

class _ResultsList extends StatelessWidget {
  final List<PriceFinderResult> items;

  const _ResultsList({required this.items});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(
            'No products found. Try "Rice", "Ramen", "Milk", "Detergent", or "USB-C".',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6)),
          ),
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      itemCount: items.length,
      itemBuilder: (context, index) => Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: _ProductCard(result: items[index]),
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  final PriceFinderResult result;

  const _ProductCard({required this.result});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              result.productName,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 2),
            Text(
              result.category.displayName,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.55)),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: ZenColors.matchaLight,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.lightbulb_outline_rounded, size: 18, color: ZenColors.matchaDark),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          result.recommendation.label,
                          style: Theme.of(context)
                              .textTheme
                              .bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w700, color: ZenColors.matchaDark),
                        ),
                        const SizedBox(height: 2),
                        Text(result.recommendation.detail, style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            ...result.comparisons.map((c) => _StoreRow(comparison: c)),
          ],
        ),
      ),
    );
  }
}

class _StoreRow extends ConsumerWidget {
  final StoreComparison comparison;

  const _StoreRow({required this.comparison});

  (IconData, Color, String) get _trendVisual {
    switch (comparison.priceTrend) {
      case PriceTrend.rising:
        return (Icons.trending_up_rounded, const Color(0xFFC1543C), 'Rising');
      case PriceTrend.falling:
        return (Icons.trending_down_rounded, ZenColors.matchaDark, 'Falling');
      case PriceTrend.stable:
        return (Icons.trending_flat_rounded, ZenColors.sumi, 'Stable');
      case PriceTrend.insufficientData:
        return (Icons.remove_rounded, ZenColors.sumi, 'Not enough data');
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final (icon, color, label) = _trendVisual;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  comparison.storeName,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                  overflow: TextOverflow.ellipsis,
                ),
                Row(
                  children: [
                    Text(
                      '${comparison.storeType.displayName} · ',
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.55)),
                    ),
                    Icon(Icons.star_rounded, size: 13, color: ZenColors.sumi.withValues(alpha: 0.55)),
                    Text(
                      comparison.rating.toStringAsFixed(1) + (comparison.inStock ? '' : ' · Out of stock'),
                      style: Theme.of(context)
                          .textTheme
                          .bodySmall
                          ?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.55)),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Icon(icon, size: 14, color: color),
                    const SizedBox(width: 3),
                    Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: color)),
                  ],
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                formatKrwForDisplay(ref, comparison.trueEconomicCostKrw),
                style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800),
              ),
              Text(
                '${formatKrwForDisplay(ref, comparison.priceKrw)} + ${formatKrwForDisplay(ref, comparison.transitCostKrw)} transit',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.55)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
