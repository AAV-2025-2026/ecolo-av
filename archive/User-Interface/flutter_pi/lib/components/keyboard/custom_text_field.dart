import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'input_manager.dart';

class CustomTextField extends StatelessWidget {
  final String fieldId;
  final String hint;

  const CustomTextField({
    super.key,
    required this.fieldId,
    required this.hint,
  });

  @override
  Widget build(BuildContext context) {
    final input = context.watch<InputManager>();
    final text = input.textFor(fieldId);

    return GestureDetector(
      onTap: () => context.read<InputManager>().focusField(fieldId),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        decoration: BoxDecoration(
          border: Border.all(color: Colors.grey),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          text.isEmpty ? hint : text,
          style: TextStyle(
            color: text.isEmpty ? Colors.grey : Colors.black,
          ),
        ),
      ),
    );
  }
}
