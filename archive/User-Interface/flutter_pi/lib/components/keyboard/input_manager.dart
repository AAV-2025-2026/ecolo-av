import 'package:flutter/foundation.dart';

class InputManager extends ChangeNotifier {
  final Map<String, String> _texts = {};  // fieldId -> text
  String? _activeFieldId;
  bool _keyboardVisible = false;

  String textFor(String fieldId) => _texts[fieldId] ?? "";

  bool get keyboardVisible => _keyboardVisible;

  void focusField(String fieldId) {
    _activeFieldId = fieldId;
    _keyboardVisible = true;
    notifyListeners();
  }

  void blur() {
    _activeFieldId = null;
    _keyboardVisible = false;
    notifyListeners();
  }

  void insert(String value) {
    if (_activeFieldId == null) return;

    final current = _texts[_activeFieldId] ?? "";
    _texts[_activeFieldId!] = current + value;
    notifyListeners();
  }

  void backspace() {
    if (_activeFieldId == null) return;
    final current = _texts[_activeFieldId] ?? "";
    if (current.isNotEmpty) {
      _texts[_activeFieldId!] = current.substring(0, current.length - 1);
      notifyListeners();
    }
  }
}
