import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

class SkeletonLoader extends StatelessWidget {
  final Widget child;
  final bool loading;

  const SkeletonLoader({super.key, required this.child, this.loading = true});

  @override
  Widget build(BuildContext context) {
    if (!loading) return child;
    return Shimmer.fromColors(
      baseColor: Colors.grey.shade800,
      highlightColor: Colors.grey.shade700,
      child: child,
    );
  }
}
