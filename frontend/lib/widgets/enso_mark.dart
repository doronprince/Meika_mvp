import 'package:flutter/material.dart';

/// The Ensō Clarity Circle brand mark: a deliberately incomplete ink ring
/// with a matcha dot at its center, evoking calm over precision.
class EnsoMark extends StatelessWidget {
  final double size;

  const EnsoMark({super.key, this.size = 36});

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/branding/logo_meika.jpeg',
      width: size,
      height: size,
      fit: BoxFit.contain,
    );
  }
}
