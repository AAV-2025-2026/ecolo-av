import 'package:flutter/material.dart';
import 'package:flutter_onscreen_keyboard/flutter_onscreen_keyboard.dart';
import 'package:flutter_pi/data/constants.dart';
import 'package:flutter_pi/screens/home_page.dart';
import 'package:window_manager/window_manager.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();

  WindowOptions windowOptions = kWindowConfig;

  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.setFullScreen(true);
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: kAppTitle,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: kColorSchemeSeed),
        useMaterial3: true,
      ),
      builder: OnscreenKeyboard.builder(
        layout: const DesktopKeyboardLayout(),
        aspectRatio: 6
      ),
      home: const MyHomePage(title: 'UI Dashboard'),
    );
  }
}
