import 'package:flutter/material.dart';

import '../core/theme/risk_colors.dart';
import '../core/theme/zen_theme.dart';
import '../data/models/survival_report.dart';

/// Savings balance month by month for the three survival scenarios. Drawn
/// directly with a painter: the app has no charting dependency, and three
/// polylines with a zero line don't justify adding one.
class RunwayChart extends StatelessWidget {
  final double startBalanceKrw;
  final List<TrajectoryPoint> points;
  final int visibleMonths;
  final String Function(num krw) formatMoney;

  const RunwayChart({
    super.key,
    required this.startBalanceKrw,
    required this.points,
    required this.visibleMonths,
    required this.formatMoney,
  });

  static const baselineColor = ZenColors.matcha;
  static const shockedColor = RiskColors.high;
  static const withCutsColor = RiskColors.moderate;

  @override
  Widget build(BuildContext context) {
    final labelStyle = Theme.of(context).textTheme.labelSmall?.copyWith(color: ZenColors.sumi.withValues(alpha: 0.6));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 200,
          width: double.infinity,
          child: CustomPaint(
            painter: _RunwayPainter(
              startBalance: startBalanceKrw,
              points: points.take(visibleMonths).toList(),
              formatMoney: formatMoney,
              labelStyle: labelStyle ?? const TextStyle(fontSize: 10),
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Wrap(
          spacing: 16,
          runSpacing: 4,
          children: [
            _LegendEntry(color: baselineColor, label: 'No shock'),
            _LegendEntry(color: shockedColor, label: 'With shocks'),
            _LegendEntry(color: withCutsColor, label: 'With shocks + cuts'),
          ],
        ),
      ],
    );
  }
}

class _LegendEntry extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendEntry({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 14, height: 3, color: color),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}

class _RunwayPainter extends CustomPainter {
  final double startBalance;
  final List<TrajectoryPoint> points;
  final String Function(num krw) formatMoney;
  final TextStyle labelStyle;

  _RunwayPainter({
    required this.startBalance,
    required this.points,
    required this.formatMoney,
    required this.labelStyle,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;

    final series = <(Color, List<double>)>[
      (RunwayChart.baselineColor, [startBalance, ...points.map((p) => p.baselineKrw)]),
      (RunwayChart.withCutsColor, [startBalance, ...points.map((p) => p.withCutsKrw)]),
      (RunwayChart.shockedColor, [startBalance, ...points.map((p) => p.shockedKrw)]),
    ];

    var maxY = 0.0;
    var minY = 0.0;
    for (final (_, values) in series) {
      for (final v in values) {
        if (v > maxY) maxY = v;
        if (v < minY) minY = v;
      }
    }
    if (maxY == minY) maxY = minY + 1;

    const topPad = 16.0;
    const bottomPad = 18.0;
    final plotHeight = size.height - topPad - bottomPad;
    final steps = points.length;

    double x(int i) => size.width * i / steps;
    double y(double v) => topPad + (maxY - v) / (maxY - minY) * plotHeight;

    final zeroY = y(0);
    final axisPaint = Paint()
      ..color = ZenColors.sandBorder
      ..strokeWidth = 1;
    for (var dx = 0.0; dx < size.width; dx += 8) {
      canvas.drawLine(Offset(dx, zeroY), Offset(dx + 4, zeroY), axisPaint);
    }

    for (final (color, values) in series) {
      final path = Path()..moveTo(x(0), y(values[0]));
      for (var i = 1; i < values.length; i++) {
        path.lineTo(x(i), y(values[i]));
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeJoin = StrokeJoin.round,
      );
    }

    void label(String text, Offset at, {bool alignRight = false}) {
      final painter = TextPainter(text: TextSpan(text: text, style: labelStyle), textDirection: TextDirection.ltr)
        ..layout();
      final dx = alignRight ? at.dx - painter.width : at.dx;
      painter.paint(canvas, Offset(dx, at.dy));
    }

    label(formatMoney(maxY), const Offset(0, 0));
    label('0', Offset(0, zeroY - 14));
    label('Today', Offset(0, size.height - 14));
    label('Month $steps', Offset(size.width, size.height - 14), alignRight: true);
  }

  @override
  bool shouldRepaint(covariant _RunwayPainter oldDelegate) {
    return oldDelegate.points != points || oldDelegate.startBalance != startBalance;
  }
}
