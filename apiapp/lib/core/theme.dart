import 'package:flutter/material.dart';

// Design tokens
const Color seedColor = Color(0xFF4A90D9);
const Color primaryColor = Color(0xFF2563EB);
const Color accentAmber = Color(0xFFF59E0B);
const Color accentGreen = Color(0xFF10B981);
const Color accentRed = Color(0xFFEF4444);
const Color accentPurple = Color(0xFF8B5CF6);
const Color surfaceColor = Color(0xFF0A0F1E);
const Color cardColor = Color(0xFF111827);
const Color borderColor = Color(0xFF1E293B);

final ColorScheme _seededLight = ColorScheme.fromSeed(
  seedColor: seedColor,
  brightness: Brightness.light,
  primary: primaryColor,
  secondary: accentAmber,
);

final ColorScheme _seededDark = ColorScheme.fromSeed(
  seedColor: seedColor,
  brightness: Brightness.dark,
  primary: primaryColor,
  secondary: accentAmber,
);

ThemeData buildLightTheme() {
  return ThemeData(
    useMaterial3: true,
    colorScheme: _seededLight.copyWith(
      surface: surfaceColor,
      onSurface: Colors.white,
    ),
    scaffoldBackgroundColor: Colors.white,
    cardColor: cardColor,
    dividerColor: borderColor,
    appBarTheme: const AppBarTheme(centerTitle: true, elevation: 0),
  );
}

ThemeData buildDarkTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: _seededDark.copyWith(surface: surfaceColor),
    scaffoldBackgroundColor: surfaceColor,
    cardColor: cardColor,
    dividerColor: borderColor,
    appBarTheme: const AppBarTheme(centerTitle: true, elevation: 0),
  );
}

// Exports
final ThemeData lightTheme = buildLightTheme();
final ThemeData darkTheme = buildDarkTheme();
