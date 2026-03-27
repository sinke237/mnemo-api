import 'package:flutter/material.dart';
import '../theme.dart';

class ConfidenceSelector extends StatelessWidget {
  final int selected; // 0,1,2
  final ValueChanged<int> onChanged;

  const ConfidenceSelector({super.key, required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Row(children: List.generate(3, (i) {
      final titles = ['Low', 'Medium', 'High'];
      final bool sel = i == selected;
      return Expanded(
        child: GestureDetector(
          onTap: () => onChanged(i),
          child: Container(
            height: 40,
            margin: const EdgeInsets.symmetric(horizontal: 4),
            decoration: BoxDecoration(
              color: sel ? (i == 2 ? accentGreen : (i == 1 ? accentAmber : accentRed)).withOpacity(0.14) : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: sel ? primaryColor : borderColor.withOpacity(0.6)),
            ),
            alignment: Alignment.center,
            child: Text(titles[i], style: TextStyle(fontWeight: sel ? FontWeight.w700 : FontWeight.w500)),
          ),
        ),
      );
    }));
  }
}
