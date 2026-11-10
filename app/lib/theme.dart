import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class C {
  static const asphalt = Color(0xFF1F2933);
  static const yellow = Color(0xFFF5B700);
  static const pothole = Color(0xFFC2410C);
  static const garbage = Color(0xFF1D4ED8);
  static const bg = Color(0xFFF7F7F4);
  static const line = Color(0xFFE4E7EB);
  static const border = Color(0xFFCBD2D9);
  static const muted = Color(0xFF52606D);
  static const body = Color(0xFF323F4B);
  static const infoBg = Color(0xFFE0F2FE), infoFg = Color(0xFF075985);
  static const warnBg = Color(0xFFFEF3C7), warnFg = Color(0xFF92400E);
  static const okBg = Color(0xFFDCFCE7), okFg = Color(0xFF166534);
  static const errBg = Color(0xFFFEE2E2), errFg = Color(0xFF991B1B);
  static const greyBg = Color(0xFFE4E7EB);

  static Color cat(String? c) => c == 'garbage' ? garbage : pothole;
}

TextStyle heading(double size) => GoogleFonts.spaceGrotesk(fontSize: size, fontWeight: FontWeight.w700, color: C.asphalt);
TextStyle urdu(double size, {Color color = C.muted}) => GoogleFonts.notoNastaliqUrdu(fontSize: size, color: color, height: 1.6);

ThemeData buildTheme() {
  final base = ThemeData(useMaterial3: true, colorScheme: ColorScheme.fromSeed(seedColor: C.yellow, primary: C.asphalt));
  return base.copyWith(
    scaffoldBackgroundColor: C.bg,
    textTheme: base.textTheme.apply(fontFamily: GoogleFonts.inter().fontFamily, bodyColor: C.asphalt, displayColor: C.asphalt),
    appBarTheme: const AppBarTheme(backgroundColor: C.bg, surfaceTintColor: Colors.transparent, foregroundColor: C.asphalt),
    snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
  );
}
