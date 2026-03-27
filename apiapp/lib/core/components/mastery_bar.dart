import 'package:flutter/material.dart';
import '../theme.dart';

class MasteryBar extends StatelessWidget {
  final double value; // 0..1

  const MasteryBar({super.key, required this.value});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Mastery',
      value: '${(value.clamp(0.0, 1.0) * 100).round()}%',
      child: Container(
        height: 6,
        decoration: BoxDecoration(
          color: borderColor.withAlpha(51),
          borderRadius: BorderRadius.circular(3),
        ),
        child: FractionallySizedBox(
          alignment: Alignment.centerLeft,
          widthFactor: value.clamp(0.0, 1.0).toDouble(),
          child: Container(
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [Color(0xFF7EE7A6), accentGreen]),
              borderRadius: BorderRadius.circular(3),
            ),
          ),
        ),
      ),
    );
  }
}
