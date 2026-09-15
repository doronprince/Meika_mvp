import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models/goal.dart';
import '../data/repositories/goal_repository.dart';

/// autoDispose: switching tabs away and back refetches, so a spending cap
/// reflects expenses logged on the Budget tab without manual invalidation.
final goalListProvider = FutureProvider.autoDispose<List<Goal>>((ref) {
  return ref.watch(goalRepositoryProvider).listGoals();
});
