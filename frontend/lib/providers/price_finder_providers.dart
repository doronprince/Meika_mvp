import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models/price_finder_result.dart';
import '../data/repositories/price_finder_repository.dart';

final priceFinderQueryProvider = StateProvider.autoDispose<String>((ref) => '');

final priceFinderResultsProvider = FutureProvider.autoDispose<List<PriceFinderResult>>((ref) {
  final query = ref.watch(priceFinderQueryProvider);
  return ref.watch(priceFinderRepositoryProvider).search(query);
});
