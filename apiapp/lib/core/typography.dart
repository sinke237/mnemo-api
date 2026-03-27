import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class MnemoTypography {
  // Headings (DM Serif Display)
  static TextStyle heading1(BuildContext c) => GoogleFonts.dmSerifDisplay(
        textStyle: Theme.of(c).textTheme.headlineLarge?.copyWith(fontSize: 36) ?? const TextStyle(fontSize: 36),
      );

  static TextStyle heading2(BuildContext c) => GoogleFonts.dmSerifDisplay(
        textStyle: Theme.of(c).textTheme.headlineMedium?.copyWith(fontSize: 28) ?? const TextStyle(fontSize: 28),
      );

  // Body (Sora)
  static TextStyle bodyLarge(BuildContext c) => GoogleFonts.sora(
        textStyle: Theme.of(c).textTheme.bodyLarge?.copyWith(fontSize: 16) ?? const TextStyle(fontSize: 16),
      );

  static TextStyle bodySmall(BuildContext c) => GoogleFonts.sora(
        textStyle: Theme.of(c).textTheme.bodySmall?.copyWith(fontSize: 12) ?? const TextStyle(fontSize: 12),
      );

  // Mono (DM Mono) for timers / ids
  static TextStyle mono(BuildContext c) => GoogleFonts.dmMono(
        textStyle: Theme.of(c).textTheme.bodyMedium?.copyWith(fontSize: 13, letterSpacing: 0.6) ?? const TextStyle(fontSize: 13),
      );

  // Labels / Tags
  static TextStyle tag(BuildContext c) => GoogleFonts.sora(
        textStyle: Theme.of(c).textTheme.labelLarge?.copyWith(fontSize: 12, fontWeight: FontWeight.w600) ?? const TextStyle(fontSize: 12),
      );
}
