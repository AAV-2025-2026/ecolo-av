import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_onscreen_keyboard/flutter_onscreen_keyboard.dart';
import 'package:flutter_pi/data/constants.dart';
import 'package:flutter_pi/screens/home_page.dart';
import 'package:flutter_pi/screens/map_page.dart';
import 'package:screen_retriever/screen_retriever.dart';
import 'package:window_manager/window_manager.dart';

Future<void> main(List<String> args) async {
  WidgetsFlutterBinding.ensureInitialized();

  final bool isMap = args.contains('--Map');

  if (!isMap) {
    _launchMap();
  }

  await windowManager.ensureInitialized();

  WindowOptions windowOptions = kWindowConfig;

  windowManager.waitUntilReadyToShow(windowOptions, () async {
    await _moveToCorrectDisplay(isMap);
    await windowManager.setFullScreen(true);
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(MyApp(isMap: isMap));
}

Future<void> _moveToCorrectDisplay(bool isMap) async {
  final displays = await screenRetriever.getAllDisplays();

  if (displays.length < 2) return;

  final display = isMap ? displays[1] : displays[0];

  final position = display.visiblePosition ?? Offset.zero;
  final size = display.visibleSize ?? display.size;

  await windowManager.setBounds(
    Rect.fromLTWH(position.dx, position.dy, size.width, size.height),
  );
}

void _launchMap() {
  final executable = Platform.resolvedExecutable;

  Process.start(
    executable,
    ['--Map'],
    mode: ProcessStartMode.detached,
  );
}

class MyApp extends StatelessWidget {
  final bool isMap;

  const MyApp({super.key, required this.isMap});
  
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
      home: isMap ? const MapPage() : const MyHomePage(title: 'UI Dashboard'),
    );
  }
}
