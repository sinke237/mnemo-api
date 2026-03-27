import 'package:flutter/material.dart';
import '../typography.dart';

enum TimerState { normal, warning, critical }

class TimerChip extends StatefulWidget {
  final Duration duration;
  final VoidCallback? onTap;

  const TimerChip({super.key, required this.duration, this.onTap});

  @override
  State<TimerChip> createState() => _TimerChipState();
}

class _TimerChipState extends State<TimerChip> {
  bool expanded = false;

  TimerState get state {
    final s = widget.duration.inSeconds.clamp(0, double.infinity);
    if (s <= 30) return TimerState.critical;
    if (s <= 120) return TimerState.warning;
    return TimerState.normal;
  }

  @override
  Widget build(BuildContext context) {
    final color = switch (state) {
      TimerState.normal => Colors.grey.shade800,
      TimerState.warning => Colors.amber.shade700,
      TimerState.critical => Colors.red.shade400,
    };

    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () {
            setState(() => expanded = !expanded);
            widget.onTap?.call();
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(_format(widget.duration), style: MnemoTypography.mono(context)),
              if (expanded) ...[
                const SizedBox(width: 8),
                Text('Tap to collapse', style: MnemoTypography.bodySmall(context)),
              ]
            ]),
          ),
        ),
      ),
    );
  }

  String _format(Duration d) {
    final clampedD = d.isNegative ? Duration.zero : d;
    final m = clampedD.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = clampedD.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '${clampedD.inHours > 0 ? '${clampedD.inHours}:' : ''}$m:$s';
  }
}
