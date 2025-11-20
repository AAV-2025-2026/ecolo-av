import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'input_manager.dart';

class KeyboardTextField extends StatefulWidget {
  const KeyboardTextField({super.key});

  @override
  State<KeyboardTextField> createState() => _CustomTextFieldState();
}

class _CustomTextFieldState extends State<KeyboardTextField> {
  final TextEditingController controller = TextEditingController();
  final FocusNode focusNode = FocusNode();

  @override
  void initState() {
    super.initState();

    focusNode.addListener(() {
      final input = Provider.of<InputManager>(context, listen: false);

      if (focusNode.hasFocus) {
        input.setActive(controller, focusNode);
      } else {
        final scope = FocusScope.of(context);
        Future.microtask(() {
          if (!mounted) return; 
          if (input.keyboardVisible &&
              input.activeFocusNode == focusNode &&
              !input.isClearingFocus) {
            scope.requestFocus(focusNode); 
          }
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      focusNode: focusNode,
      showCursor: true,
      readOnly: false,
      enableInteractiveSelection: true,
      selectAllOnFocus: false,
      decoration: const InputDecoration(border: OutlineInputBorder()),
    );
  }
}

