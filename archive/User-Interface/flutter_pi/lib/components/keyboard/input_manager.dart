import 'package:flutter/material.dart';

class InputManager extends ChangeNotifier {
  TextEditingController? _activeController;
  FocusNode? _activeFocusNode;
  bool _keyboardVisible = false;

  TextEditingController? get activeController => _activeController;
  FocusNode? get activeFocusNode => _activeFocusNode;
  bool get keyboardVisible => _keyboardVisible;

  void setActive(TextEditingController controller, FocusNode focusNode) {
    _activeController = controller;
    _activeFocusNode = focusNode;
    _keyboardVisible = true;
    notifyListeners();
  }

  bool isClearingFocus = false;

  void clearActive() {
    isClearingFocus = true;
    _keyboardVisible = false;
    _activeFocusNode?.unfocus();
    notifyListeners();
    Future.microtask(() => isClearingFocus = false);
  }

  void insert(String text) {
    final controller = _activeController;
    if (controller == null) return;

    final TextEditingValue current = controller.value;
    final TextSelection selection = current.selection;

    String newText;
    int newCursorPos;
    
    if (selection.isValid && !selection.isCollapsed) {
      newText = current.text.replaceRange(selection.start, selection.end, text);
      newCursorPos = selection.start + text.length;
    } else {
      newText = current.text.replaceRange(selection.baseOffset, selection.baseOffset, text);
      newCursorPos = selection.baseOffset + text.length;
    }

    controller.value = TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(offset: newCursorPos),
      composing: TextRange.empty, 
    );
  }

  void backspace() {
    final controller = _activeController;
    if (controller == null) return;

    final TextEditingValue current = controller.value;
    final TextSelection selection = current.selection;
    
    String newText;
    int newCursorPos;
    
    if (selection.isValid && !selection.isCollapsed) {
      newText = current.text.replaceRange(selection.start, selection.end, '');
      newCursorPos = selection.start;
    } else {
      if (selection.baseOffset <= 0) return;
      newText = current.text.replaceRange(selection.baseOffset - 1, selection.baseOffset, '');
      newCursorPos = selection.baseOffset - 1;
    }
    
    controller.value = TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(offset: newCursorPos),
      composing: TextRange.empty,
    );
  }

  void moveCursorLeft() {
    final controller = _activeController;
    if (controller == null) return;

    final pos = controller.selection.baseOffset;
    if (pos <= 0) return;

    controller.selection = TextSelection.collapsed(offset: pos - 1);
  }

  void moveCursorRight() {
    final controller = _activeController;
    if (controller == null) return;

    final pos = controller.selection.baseOffset;
    if (pos >= controller.text.length) return;

    controller.selection = TextSelection.collapsed(offset: pos + 1);
  }
}