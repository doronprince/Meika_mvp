import 'expense_category.dart';
import 'dashboard_summary.dart';

double? _nullableAmount(dynamic value) => value == null ? null : parseAmount(value);

/// Mirrors the backend's `ExposureKind` enum values byte-for-byte.
enum ExposureKind {
  socialFeed('social_feed', 'Social feed'),
  shoppingApp('shopping_app', 'Shopping app'),
  influencerContent('influencer_content', 'Influencer content'),
  adsAndDealAlerts('ads_and_deal_alerts', 'Ads & deal alerts'),
  other('other', 'Other');

  final String wireValue;
  final String displayName;

  const ExposureKind(this.wireValue, this.displayName);

  static ExposureKind fromJson(String value) {
    return ExposureKind.values.firstWhere((k) => k.wireValue == value, orElse: () => ExposureKind.other);
  }
}

class ExposureSessionEntry {
  final String id;
  final DateTime occurredOn;
  final int? startedHour;
  final String platform;
  final ExposureKind kind;
  final int minutes;

  const ExposureSessionEntry({
    required this.id,
    required this.occurredOn,
    required this.startedHour,
    required this.platform,
    required this.kind,
    required this.minutes,
  });

  factory ExposureSessionEntry.fromJson(Map<String, dynamic> json) {
    return ExposureSessionEntry(
      id: json['id'] as String,
      occurredOn: DateTime.parse(json['occurred_on'] as String),
      startedHour: json['started_hour'] as int?,
      platform: json['platform'] as String,
      kind: ExposureKind.fromJson(json['kind'] as String),
      minutes: json['minutes'] as int,
    );
  }
}

class AssociationStats {
  final double? spearmanRho;
  final double? pValue;
  final int nDays;
  final int nPermutations;

  const AssociationStats({
    required this.spearmanRho,
    required this.pValue,
    required this.nDays,
    required this.nPermutations,
  });

  factory AssociationStats.fromJson(Map<String, dynamic> json) {
    return AssociationStats(
      spearmanRho: _nullableAmount(json['spearman_rho']),
      pValue: _nullableAmount(json['p_value']),
      nDays: json['n_days'] as int,
      nPermutations: json['n_permutations'] as int,
    );
  }
}

class EffectSize {
  final int thresholdMinutes;
  final int highDays;
  final int zeroDays;
  final double meanAfterHighKrw;
  final double meanAfterZeroKrw;
  final double differenceKrw;

  const EffectSize({
    required this.thresholdMinutes,
    required this.highDays,
    required this.zeroDays,
    required this.meanAfterHighKrw,
    required this.meanAfterZeroKrw,
    required this.differenceKrw,
  });

  factory EffectSize.fromJson(Map<String, dynamic> json) {
    return EffectSize(
      thresholdMinutes: json['high_exposure_threshold_minutes'] as int,
      highDays: json['high_days'] as int,
      zeroDays: json['zero_days'] as int,
      meanAfterHighKrw: parseAmount(json['mean_spend_after_high_krw']),
      meanAfterZeroKrw: parseAmount(json['mean_spend_after_zero_krw']),
      differenceKrw: parseAmount(json['difference_krw']),
    );
  }
}

class Intervention {
  final bool triggered;
  final int todayMinutes;
  final int? thresholdMinutes;
  final String? topPlatform;
  final String message;
  final String? suggestion;

  const Intervention({
    required this.triggered,
    required this.todayMinutes,
    required this.thresholdMinutes,
    required this.topPlatform,
    required this.message,
    required this.suggestion,
  });

  factory Intervention.fromJson(Map<String, dynamic> json) {
    return Intervention(
      triggered: json['triggered'] as bool,
      todayMinutes: json['today_minutes'] as int,
      thresholdMinutes: json['threshold_minutes'] as int?,
      topPlatform: json['top_platform'] as String?,
      message: json['message'] as String,
      suggestion: json['suggestion'] as String?,
    );
  }
}

class ExposureInsightReport {
  final String state;
  final int trackedDays;
  final int daysWithExposure;
  final int minutesLogged;
  final String? verdict;
  final AssociationStats? primary;
  final List<(int, AssociationStats)> lags;
  final List<(ExposureKind, int, AssociationStats)> byKind;
  final EffectSize? effect;
  final Intervention intervention;
  final List<ClarityFactor> factors;
  final List<String> limitations;

  const ExposureInsightReport({
    required this.state,
    required this.trackedDays,
    required this.daysWithExposure,
    required this.minutesLogged,
    required this.verdict,
    required this.primary,
    required this.lags,
    required this.byKind,
    required this.effect,
    required this.intervention,
    required this.factors,
    required this.limitations,
  });

  bool get computed => state == 'computed';
  bool get associationFound => verdict == 'association';

  factory ExposureInsightReport.fromJson(Map<String, dynamic> json) {
    return ExposureInsightReport(
      state: json['state'] as String,
      trackedDays: json['tracked_days'] as int,
      daysWithExposure: json['days_with_exposure'] as int,
      minutesLogged: json['minutes_logged'] as int,
      verdict: json['verdict'] as String?,
      primary: json['primary'] == null ? null : AssociationStats.fromJson(json['primary'] as Map<String, dynamic>),
      lags: (json['exploratory_lags'] as List).map((l) {
        final m = l as Map<String, dynamic>;
        return (m['lag_days'] as int, AssociationStats.fromJson(m));
      }).toList(),
      byKind: (json['by_kind'] as List).map((k) {
        final m = k as Map<String, dynamic>;
        return (ExposureKind.fromJson(m['kind'] as String), m['minutes_total'] as int, AssociationStats.fromJson(m));
      }).toList(),
      effect: json['effect'] == null ? null : EffectSize.fromJson(json['effect'] as Map<String, dynamic>),
      intervention: Intervention.fromJson(json['intervention'] as Map<String, dynamic>),
      factors: (json['factors'] as List).map((f) => ClarityFactor.fromJson(f as Map<String, dynamic>)).toList(),
      limitations: (json['limitations'] as List).cast<String>(),
    );
  }
}
