import 'package:flutter/material.dart';

class KeyboardKey extends StatelessWidget {
  final Widget child;
  final VoidCallback? onPressed;
  final double minWidth;
  final double minHeight;
  final Color? backgroundColor;

  const KeyboardKey({
    super.key,
    required this.child,
    this.onPressed,
    this.minWidth = 45,
    this.minHeight = 45,
    this.backgroundColor,
  });

  @override
  Widget build(BuildContext context) {
    return Focus(
      canRequestFocus: false,
      skipTraversal: true,
      child: SizedBox(
        width: minWidth,
        height: minHeight,
        child: TextButton(
          style: TextButton.styleFrom(
            backgroundColor: backgroundColor ?? Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(6),
            ),
            foregroundColor: Colors.black,
          ),
          onPressed: onPressed,
          child: child,
        ),
      ),
    );
  }
}