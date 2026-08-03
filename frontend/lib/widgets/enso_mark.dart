import 'package:flutter/material.dart';

import '../core/theme/zen_theme.dart';

/// The Ensō Clarity Circle brand mark: a deliberately incomplete ink ring
/// with a matcha dot at its center, evoking calm over precision.
class EnsoMark extends StatelessWidget {
  final double size;

  const EnsoMark({super.key, this.size = 36});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(painter: _EnsoPainter()),
    );
  }
}

class _EnsoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 2;

    final ringPaint = Paint()
      ..color = ZenColors.sumi
      ..style = PaintingStyle.stroke
      ..strokeWidth = size.width * 0.06
      ..strokeCap = StrokeCap.round;

    // ~315° arc — an intentional gap, the Ensō's imperfection.
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -1.65,
      5.5,
      false,
      ringPaint,
    );

    final dotPaint = Paint()..color = ZenColors.matcha;
    canvas.drawCircle(center, size.width * 0.12, dotPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
