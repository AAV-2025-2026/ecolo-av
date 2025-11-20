import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../components/keyboard/input_manager.dart';
import '../components/keyboard/keyboard_text_field.dart';
import '../components/keyboard/keyboard.dart';

class KeyboardPage extends StatelessWidget {
  const KeyboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => InputManager(),
      child: Scaffold(
        body: SafeArea(
          child: Column(
            children: [
              const SizedBox(height: 20),

              KeyboardTextField(),
              KeyboardTextField(),
              KeyboardTextField(),

              const Spacer(),

              Consumer<InputManager>(
                builder: (context, input, _) {
                  return input.keyboardVisible
                      ? FocusScope(
                          canRequestFocus: false,
                          descendantsAreFocusable: false,
                          child: const Keyboard(),
                        )
                      : const SizedBox.shrink();
                },
              ),
            ],
          ),
        ),
      )
    );
  }
}
