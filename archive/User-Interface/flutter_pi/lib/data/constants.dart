import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';

const kWindowConfig = WindowOptions(
    size: Size(1920, 1080),
    center: true,
    backgroundColor: Colors.transparent,
    skipTaskbar: false,
    titleBarStyle: TitleBarStyle.hidden,
);

const kAppTitle = 'ROS2 + Flask + Flutter Demo';

const kColorSchemeSeed = Colors.deepPurple;

const kOsrmBaseUrl = 'http://localhost:5000';