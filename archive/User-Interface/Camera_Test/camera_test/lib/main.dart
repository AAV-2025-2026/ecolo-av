import 'package:flutter/material.dart';
import 'screens/blank_camera.dart';

void main() {
  runApp(const CameraClientApp());
}

class CameraClientApp extends StatelessWidget {
  const CameraClientApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: BlankCameraPage(),
    );
  }
}
