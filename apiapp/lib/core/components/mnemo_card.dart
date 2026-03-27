import 'package:flutter/material.dart';
import '../theme.dart';

class MnemoCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;

  const MnemoCard({super.key, required this.child, this.padding = const EdgeInsets.all(8)});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: cardColor,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: borderColor.withAlpha(153)),
      ),
      child: child,
    );
  }
}
