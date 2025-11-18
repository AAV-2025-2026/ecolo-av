import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'input_manager.dart';
import 'custom_button.dart';

class CustomKeyboard extends StatelessWidget {
  const CustomKeyboard({super.key});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final totalWidth = constraints.maxWidth;
        final mainKeyboardWidth = totalWidth * 6.5 / 9;
        final numberPadWidth = totalWidth * 2 / 9;

        // First row normal keys (excluding Backspace)
        const normalKeysInFirstRow = 10;
        const backspaceFlex = 1.5;

        // Calculate key width, half-key space between pads
        final keyWidth = (mainKeyboardWidth - 0.5 * mainKeyboardWidth / (normalKeysInFirstRow + backspaceFlex)) /
            (normalKeysInFirstRow + backspaceFlex);

        const keyHeight = 60.0;
        const keyPadding = 3.0;

        Widget buildKey(String label,
            {double? width, double? height, VoidCallback? onTap, double flexMultiplier = 1}) {
          return SizedBox(
            width: width ?? keyWidth * flexMultiplier,
            height: height ?? keyHeight,
            child: Padding(
              padding: const EdgeInsets.all(keyPadding),
              child: CustomButton(
                onPressed: onTap,
                child: Center(
                  child: Text(
                    label,
                    style: const TextStyle(fontSize: 18),
                  ),
                ),
              ),
            ),
          );
        }

        Widget buildRow(List<String> keys) {
          final input = context.read<InputManager>();
          return Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: keys.map((key) {
              switch (key) {
                case 'Backspace':
                  return buildKey('←', flexMultiplier: backspaceFlex, onTap: input.backspace);
                case 'Enter':
                  return buildKey('Enter', flexMultiplier: 2, onTap: () => input.insert(' '));
                case 'Space':
                  return buildKey(' ', flexMultiplier: 4.5, onTap: () => input.insert(' '));
                case '<':
                  return buildKey('<', flexMultiplier: 1, onTap: () => input.insert(' '));
                case '>':
                  return buildKey('>', flexMultiplier: 1, onTap: () => input.insert(' '));
                case 'Close':
                  return buildKey('⬇', flexMultiplier: 1.5, onTap: () => input.insert(' '));
                case 'Symbol':
                  return buildKey('?#&', flexMultiplier: 1.5, onTap: () => input.insert(' '));
                case 'Keyboard Switch':
                  return buildKey('🌐', flexMultiplier: 1.5, onTap: () => input.insert(' '));
                default:
                  return buildKey(key, onTap: () => input.insert(key));
              }
            }).toList(),
          );
        }

        Widget buildNumberPad(List<List<String>> padRows) {
          final input = context.read<InputManager>();
          return Column(
            mainAxisSize: MainAxisSize.min,
            children: padRows.map((row) {
              return Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: row.map((key) {
                  return buildKey(key, width: keyWidth, height: keyHeight, onTap: () => input.insert(key));
                }).toList(),
              );
            }).toList(),
          );
        }

        return Container(
          color: Colors.grey[100],
          padding: const EdgeInsets.all(6),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // main keyboard 
              SizedBox(
                width: mainKeyboardWidth,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    buildRow(_row1),
                    buildRow(_row2),
                    buildRow(_row3),
                    buildRow(_row4),
                  ],
                ),
              ),

              SizedBox(width: keyWidth / 2),

              // number pad 
              SizedBox(
                width: numberPadWidth,
                child: buildNumberPad(_numberPad),
              ),
            ],
          ),
        );
      },
    );
  }

  static const _row1 = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', 'Backspace'];
  static const _row2 = ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'Enter'];
  static const _row3 = ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '-'];
  static const _row4 = ['Close', 'Keyboard Switch', 'Space', 'Symbol', '<', '>'];
  static const _numberPad = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['0'],
  ];
}
