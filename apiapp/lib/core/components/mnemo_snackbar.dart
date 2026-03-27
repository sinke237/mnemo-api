import 'package:flutter/material.dart';

enum MnemoSnackbarType { info, success, error, warning }

class MnemoSnackbar {
  static void show(BuildContext context, String message, {MnemoSnackbarType type = MnemoSnackbarType.info}) {
    final color = switch (type) {
      MnemoSnackbarType.info => Colors.blueGrey,
      MnemoSnackbarType.success => Colors.green,
      MnemoSnackbarType.error => Colors.red,
      MnemoSnackbarType.warning => Colors.amber,
    };

    final snack = SnackBar(
      content: Text(message),
      backgroundColor: color,
      duration: const Duration(seconds: 4),
    );
    ScaffoldMessenger.of(context).showSnackBar(snack);
  }
}
