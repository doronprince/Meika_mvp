import 'package:flutter/material.dart';

import '../../data/models/dashboard_summary.dart';
import 'zen_theme.dart';

/// Shared risk-level → color mapping for the clarity score ring, budget
/// progress bars, and any other Phase 6+ surface that renders [RiskLevel].
class RiskColors {
  RiskColors._();

  static const low = ZenColors.matcha;
  static const moderate = Color(0xFFC98A3A);
  static const high = Color(0xFFC1543C);

  static Color forLevel(RiskLevel level) {
    switch (level) {
      case RiskLevel.low:
        return low;
      case RiskLevel.moderate:
        return moderate;
      case RiskLevel.high:
        return high;
    }
  }
}
