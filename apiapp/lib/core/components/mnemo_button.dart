import 'package:flutter/material.dart';
import '../theme.dart';

enum MnemoButtonVariant { primary, ghost }

class MnemoButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final MnemoButtonVariant variant;

  const MnemoButton({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.variant = MnemoButtonVariant.primary,
  });

  @override
  Widget build(BuildContext context) {
    final bool disabled = onPressed == null || loading;
    final ButtonStyle style = variant == MnemoButtonVariant.primary
        ? ElevatedButton.styleFrom(
            backgroundColor: primaryColor,
            minimumSize: const Size.fromHeight(52),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          )
        : OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(52),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            side: BorderSide(color: borderColor),
          );

    final child = loading
        ? SizedBox(
            height: 20,
            width: 140,
            child: LinearProgressIndicator(backgroundColor: const Color.fromRGBO(255, 255, 255, 0.06), valueColor: AlwaysStoppedAnimation(primaryColor),
            ),
          )
        : Text(label);

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200),
      opacity: disabled ? 0.4 : 1.0,
      child: variant == MnemoButtonVariant.primary
          ? ElevatedButton(onPressed: disabled ? null : onPressed, style: style, child: child)
          : OutlinedButton(onPressed: disabled ? null : onPressed, style: style, child: child),
    );
  }
}
