import 'package:flutter/material.dart';
import '../theme.dart';

class ConfidenceSelector extends StatelessWidget {
  final int selected; // 0,1,2
  final ValueChanged<int> onChanged;

  const ConfidenceSelector({super.key, required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<int>(
      segments: const <ButtonSegment<int>>[
        ButtonSegment<int>(value: 0, label: Text('Low')),
        ButtonSegment<int>(value: 1, label: Text('Medium')),
        ButtonSegment<int>(value: 2, label: Text('High')),
      ],
      selected: <int>{selected},
      onSelectionChanged: (Set<int> newSelection) {
        onChanged(newSelection.first);
      },
      style: ButtonStyle(
        backgroundColor: WidgetStateProperty.resolveWith<Color>(
          (Set<WidgetState> states) {
            if (states.contains(WidgetState.selected)) {
              if (selected == 0) {
                return accentRed.withAlpha(35);
              } else if (selected == 1) {
                return accentAmber.withAlpha(35);
              } else {
                return accentGreen.withAlpha(35);
              }
            }
            return Colors.transparent;
          },
        ),
        foregroundColor: WidgetStateProperty.all<Color>(Colors.white),
        side: WidgetStateProperty.all<BorderSide>(
          BorderSide(color: borderColor.withAlpha(153)),
        ),
      ),
    );
  }
}
