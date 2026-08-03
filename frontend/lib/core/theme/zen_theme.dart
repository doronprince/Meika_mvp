import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// The Zen Garden palette. Values must stay byte-identical to the backend's
/// design tokens (see brand spec) — this is the single source of truth for
/// the Flutter client.
class ZenColors {
  ZenColors._();

  static const washi = Color(0xFFFBFBF7);
  static const sumi = Color(0xFF2F2F2F);
  static const matcha = Color(0xFF889A7B);
  static const matchaDark = Color(0xFF6E8062);
  static const matchaLight = Color(0xFFE9EFE6);
  static const sandBorder = Color(0xFFE4E4D8);
  static const cardBg = Color(0xFFFFFFFF);
}

class ZenTheme {
  ZenTheme._();

  static ThemeData get light {
    final textTheme = GoogleFonts.figtreeTextTheme().apply(
      bodyColor: ZenColors.sumi,
      displayColor: ZenColors.sumi,
    );

    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: ZenColors.washi,
      colorScheme: ColorScheme.fromSeed(
        seedColor: ZenColors.matcha,
        brightness: Brightness.light,
      ).copyWith(
        primary: ZenColors.matcha,
        secondary: ZenColors.matchaDark,
        surface: ZenColors.washi,
      ),
      textTheme: textTheme,
      appBarTheme: const AppBarTheme(
        backgroundColor: ZenColors.washi,
        foregroundColor: ZenColors.sumi,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
      ),
      cardTheme: CardThemeData(
        color: ZenColors.cardBg,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: ZenColors.sandBorder),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: ZenColors.matcha,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        ),
      ),
      dividerColor: ZenColors.sandBorder,
    );
  }
}
