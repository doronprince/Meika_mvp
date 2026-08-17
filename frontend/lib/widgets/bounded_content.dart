import 'package:flutter/material.dart';

/// Caps content width and centers it — without this, a `ListView` fills the
/// full browser width on desktop/web, stretching card rows so a
/// `spaceBetween` label and value end up hundreds of pixels apart instead of
/// reading as one line.
class BoundedContent extends StatelessWidget {
  final Widget child;
  final double maxWidth;

  const BoundedContent({super.key, required this.child, this.maxWidth = 520});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );
  }
}
