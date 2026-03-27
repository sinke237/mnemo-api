import 'package:flutter/material.dart';
import '../typography.dart';

class TagChip extends StatelessWidget {
  final String label;
  final bool removable;
  final bool selected;
  final VoidCallback? onRemove;

  const TagChip({super.key, required this.label, this.removable = false, this.selected = false, this.onRemove})
      : assert(!removable || onRemove != null);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: selected ? Colors.blueAccent.withAlpha(40) : Colors.grey.withAlpha(15),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(label, style: MnemoTypography.tag(context)),
        if (removable) ...[
          const SizedBox(width: 8),
          IconButton(
            onPressed: onRemove,
            icon: const Icon(Icons.close, size: 14),
            tooltip: 'Remove',
          ),
        ]
      ]),
    );
  }
}
