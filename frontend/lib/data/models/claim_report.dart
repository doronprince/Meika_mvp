import 'dashboard_summary.dart';
import 'expense_category.dart';

double? _nullableAmount(dynamic value) => value == null ? null : parseAmount(value);

class ScorePart {
  final String label;
  final int points;

  const ScorePart({required this.label, required this.points});

  factory ScorePart.fromJson(Map<String, dynamic> json) =>
      ScorePart(label: json['label'] as String, points: json['points'] as int);
}

class ClaimSource {
  final int position;
  final String title;
  final String link;
  final String domain;
  final String tier;
  final int credibility;
  final int independence;
  final List<ScorePart> conflictSignals;
  final bool relevant;
  final String stance;
  final int? echoOf;

  const ClaimSource({
    required this.position,
    required this.title,
    required this.link,
    required this.domain,
    required this.tier,
    required this.credibility,
    required this.independence,
    required this.conflictSignals,
    required this.relevant,
    required this.stance,
    required this.echoOf,
  });

  factory ClaimSource.fromJson(Map<String, dynamic> json) {
    return ClaimSource(
      position: json['position'] as int,
      title: json['title'] as String,
      link: json['link'] as String,
      domain: json['domain'] as String,
      tier: json['tier'] as String,
      credibility: json['credibility'] as int,
      independence: json['independence'] as int,
      conflictSignals: (json['conflict_signals'] as List)
          .map((p) => ScorePart.fromJson(p as Map<String, dynamic>))
          .toList(),
      relevant: json['relevant'] as bool,
      stance: json['stance'] as String,
      echoOf: json['echo_of'] as int?,
    );
  }
}

class CautionComponent {
  final String key;
  final String name;
  final int cap;
  final double? points;
  final bool computable;
  final String detail;

  const CautionComponent({
    required this.key,
    required this.name,
    required this.cap,
    required this.points,
    required this.computable,
    required this.detail,
  });

  factory CautionComponent.fromJson(Map<String, dynamic> json) {
    return CautionComponent(
      key: json['key'] as String,
      name: json['name'] as String,
      cap: json['cap'] as int,
      points: _nullableAmount(json['points']),
      computable: json['computable'] as bool,
      detail: json['detail'] as String,
    );
  }
}

class ClaimPersonalContext {
  final double budgetHeadroomKrw;
  final double? budgetRunwayDays;
  final double? survivalRunwayDays;
  final double? exposure;

  const ClaimPersonalContext({
    required this.budgetHeadroomKrw,
    required this.budgetRunwayDays,
    required this.survivalRunwayDays,
    required this.exposure,
  });

  factory ClaimPersonalContext.fromJson(Map<String, dynamic> json) {
    return ClaimPersonalContext(
      budgetHeadroomKrw: parseAmount(json['budget_headroom_krw']),
      budgetRunwayDays: _nullableAmount(json['budget_runway_days']),
      survivalRunwayDays: _nullableAmount(json['survival_runway_days']),
      exposure: _nullableAmount(json['exposure']),
    );
  }
}

/// A frozen claim evaluation. The caution score is NOT a truth score.
class ClaimReport {
  final String id;
  final String claimText;
  final String claimType;
  final String evidenceStatus;
  final int? evidenceAgeDays;
  final String evidenceStance;
  final int? cautionScore;
  final int? cautionScoreUpper;
  final RiskLevel? riskLevel;
  final int sourceCount;
  final double? stakeAmountKrw;
  final ClaimPersonalContext personal;
  final List<CautionComponent> components;
  final List<ClaimSource> sources;
  final List<ClarityFactor> factors;
  final List<String> limitations;
  final String disclaimer;

  const ClaimReport({
    required this.id,
    required this.claimText,
    required this.claimType,
    required this.evidenceStatus,
    required this.evidenceAgeDays,
    required this.evidenceStance,
    required this.cautionScore,
    required this.cautionScoreUpper,
    required this.riskLevel,
    required this.sourceCount,
    required this.stakeAmountKrw,
    required this.personal,
    required this.components,
    required this.sources,
    required this.factors,
    required this.limitations,
    required this.disclaimer,
  });

  factory ClaimReport.fromJson(Map<String, dynamic> json) {
    return ClaimReport(
      id: json['id'] as String,
      claimText: json['claim_text'] as String,
      claimType: json['claim_type'] as String,
      evidenceStatus: json['evidence_status'] as String,
      evidenceAgeDays: json['evidence_age_days'] as int?,
      evidenceStance: json['evidence_stance'] as String,
      cautionScore: json['caution_score'] as int?,
      cautionScoreUpper: json['caution_score_upper'] as int?,
      riskLevel: json['risk_level'] == null ? null : RiskLevel.fromJson(json['risk_level'] as String),
      sourceCount: json['source_count'] as int,
      stakeAmountKrw: _nullableAmount(json['stake_amount_krw']),
      personal: ClaimPersonalContext.fromJson(json['personal'] as Map<String, dynamic>),
      components: (json['components'] as List)
          .map((c) => CautionComponent.fromJson(c as Map<String, dynamic>))
          .toList(),
      sources: (json['sources'] as List).map((s) => ClaimSource.fromJson(s as Map<String, dynamic>)).toList(),
      factors: (json['factors'] as List).map((f) => ClarityFactor.fromJson(f as Map<String, dynamic>)).toList(),
      limitations: (json['limitations'] as List).cast<String>(),
      disclaimer: json['disclaimer'] as String,
    );
  }
}

class ClaimSummary {
  final String id;
  final String claimText;
  final int? cautionScore;
  final int? cautionScoreUpper;
  final RiskLevel? riskLevel;

  const ClaimSummary({
    required this.id,
    required this.claimText,
    required this.cautionScore,
    required this.cautionScoreUpper,
    required this.riskLevel,
  });

  factory ClaimSummary.fromJson(Map<String, dynamic> json) {
    return ClaimSummary(
      id: json['id'] as String,
      claimText: json['claim_text'] as String,
      cautionScore: json['caution_score'] as int?,
      cautionScoreUpper: json['caution_score_upper'] as int?,
      riskLevel: json['risk_level'] == null ? null : RiskLevel.fromJson(json['risk_level'] as String),
    );
  }
}
