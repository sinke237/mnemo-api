import 'package:flutter/material.dart';

class DegradedApiBanner extends StatelessWidget {
  final String message;

  const DegradedApiBanner({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: Colors.amber.shade700,
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
      child: Row(children: [
        const Icon(Icons.warning_amber_outlined, color: Colors.black87),
        const SizedBox(width: 8),
        Expanded(child: Text(message, style: const TextStyle(color: Colors.black87))),
      ]),
    );
  }
}
