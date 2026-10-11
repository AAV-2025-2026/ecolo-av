import 'package:flutter/material.dart';

/// The home screen's e-stop: big, red, one tap. It only ever sets the e-stop; clearing
/// it is a person's deliberate act, from a laptop.
class EstopButton extends StatelessWidget {
  const EstopButton({super.key, required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Emergency stop',
      child: SizedBox(
        width: 190,
        height: 130,
        child: ElevatedButton(
          key: const Key('estop'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.red.shade700,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
            ),
            side: const BorderSide(color: Colors.white, width: 3),
          ),
          onPressed: onPressed,
          // Scaled to fit, so a big text setting can't push the label out of the button.
          child: const FittedBox(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.pan_tool, size: 40),
                SizedBox(height: 6),
                Text(
                  'E-STOP',
                  style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
