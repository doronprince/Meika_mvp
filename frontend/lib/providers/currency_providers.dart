import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/format/currency.dart';
import '../core/locale/region_currency.dart';
import '../data/models/user_profile.dart';
import '../data/repositories/fx_repository.dart';
import '../data/repositories/user_repository.dart';

/// A best-effort default from the device's locale — only used until the
/// real profile loads (or if it fails to load).
final deviceCurrencyProvider = Provider<String>((ref) {
  final locale = WidgetsBinding.instance.platformDispatcher.locale;
  return currencyForCountryCode(locale.countryCode);
});

final userProfileProvider = FutureProvider.autoDispose<UserProfile>((ref) {
  return ref.watch(userRepositoryProvider).getProfile();
});

/// Live KRW → X rates. Refreshed whenever this provider is re-watched after
/// disposal (autoDispose) — good enough for a rate that only meaningfully
/// moves hour to hour, not a persistent background poll.
final fxRatesProvider = FutureProvider.autoDispose<Map<String, double>>((ref) {
  return ref.watch(fxRepositoryProvider).getRates(base: 'KRW');
});

/// The currency to display amounts in: the user's saved preference once
/// loaded, falling back to a locale-based guess while it loads or if it
/// fails to load (e.g. signed out).
final preferredCurrencyProvider = Provider.autoDispose<String>((ref) {
  final profile = ref.watch(userProfileProvider);
  return profile.whenOrNull(data: (p) => p.preferredCurrency) ?? ref.watch(deviceCurrencyProvider);
});

/// Converts a KRW amount into the current preferred currency and formats
/// it. Falls back to plain KRW formatting if rates haven't loaded yet or
/// the preferred currency has no live rate — never blocks rendering on a
/// network round trip.
String formatKrwForDisplay(WidgetRef ref, num krwAmount) {
  final currency = ref.watch(preferredCurrencyProvider);
  if (currency == 'KRW') return formatKrw(krwAmount);

  final rates = ref.watch(fxRatesProvider).valueOrNull;
  final rate = rates?[currency];
  if (rate == null) return formatKrw(krwAmount);

  return formatCurrency(krwAmount * rate, currency);
}
