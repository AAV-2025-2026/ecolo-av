import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_onscreen_keyboard/flutter_onscreen_keyboard.dart';
import 'package:flutter_pi/data/constants.dart';
import 'package:flutter_pi/screens/home_page.dart';
import 'package:flutter_pi/screens/map_page.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:screen_retriever/screen_retriever.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:window_manager/window_manager.dart';



Future<void> main(List<String> args) async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize WebRTC on Linux (Raspberry Pi)
  if (Platform.isLinux) {
    await WebRTC.initialize();
  }

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

  // Required for desktop (Windows/Mac/Linux)
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;
  
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
      debugShowCheckedModeBanner: kDebugMode,
      title: kAppTitle,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: kColorSchemeSeed),
        useMaterial3: true,
      ),
      builder: OnscreenKeyboard.builder(
        layout: const DesktopKeyboardLayout(),
        aspectRatio: 6,
      ),
      home: isMap
          ? const MapPageController()
          : const MyHomePage(title: 'UI Dashboard'),
    );
  }
}